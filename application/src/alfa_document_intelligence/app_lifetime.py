"""Window presence tracking and automatic shutdown of the local server (REQ-101).

The browser windows opened by the launcher send a heartbeat while they are
visible and a "closing" notice when they are closed.  ``WindowPresence`` turns
those signals into a ``should_stop()`` decision; ``AppLifetime`` runs a guard
thread that stops the server when that decision is true or when an explicit
exit was requested.
"""
from __future__ import annotations

import re
import threading
import time
from typing import Callable

_WINDOW_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


def _check_window_id(window_id: str) -> str:
    if not isinstance(window_id, str) or _WINDOW_ID.fullmatch(window_id) is None:
        raise ValueError("invalid window id")
    return window_id


class WindowPresence:
    """Tracks live windows; thread-safe (server thread writes, guard thread reads)."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        *,
        heartbeat_expiry_seconds: float = 180.0,
        closing_grace_seconds: float = 10.0,
        startup_grace_seconds: float = 120.0,
    ) -> None:
        self._clock = clock
        self._expiry = heartbeat_expiry_seconds
        self._closing_grace = closing_grace_seconds
        self._startup_grace = startup_grace_seconds
        self._lock = threading.Lock()
        self._started = clock()
        self._last_beat: dict[str, float] = {}
        self._ever_seen = False
        self._last_closing: float | None = None
        self._last_activity: float | None = None

    def heartbeat(self, window_id: str) -> None:
        _check_window_id(window_id)
        with self._lock:
            now = self._clock()
            self._last_beat[window_id] = now
            self._ever_seen = True
            self._last_activity = now

    def closing(self, window_id: str) -> None:
        _check_window_id(window_id)
        with self._lock:
            now = self._clock()
            self._last_beat.pop(window_id, None)
            self._last_closing = now
            self._last_activity = now

    def activity(self) -> None:
        with self._lock:
            self._last_activity = self._clock()

    def should_stop(self) -> bool:
        with self._lock:
            now = self._clock()
            if any(now - beat < self._expiry for beat in self._last_beat.values()):
                return False
            if not self._ever_seen:
                return now - self._started >= self._startup_grace
            if self._last_closing is not None and not self._last_beat:
                # Last window closed explicitly: stop after a quiet grace period.
                quiet_since = max(self._last_closing, self._last_activity or 0.0)
                return now - quiet_since >= self._closing_grace
            # All remaining windows went silent without closing.
            return True


class AppLifetime:
    """Guard thread that stops the server once; ``request_exit`` only sets a flag."""

    def __init__(
        self,
        presence: WindowPresence,
        stop_server: Callable[[], None],
        *,
        poll_seconds: float = 1.0,
    ) -> None:
        self._presence = presence
        self._stop_server = stop_server
        self._poll = poll_seconds
        self._exit = threading.Event()
        self._start_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.stopped = threading.Event()

    def start(self) -> None:
        with self._start_lock:
            if self._thread is not None:
                return
            self._thread = threading.Thread(target=self._guard, name="ocr2-app-lifetime", daemon=True)
            self._thread.start()

    def request_exit(self) -> None:
        # Never call the server shutdown here: this runs inside a request on the
        # server thread and shutdown() would deadlock.
        self._exit.set()

    def _guard(self) -> None:
        while not self._exit.wait(self._poll):
            if self._presence.should_stop():
                break
        try:
            self._stop_server()
        finally:
            self.stopped.set()
