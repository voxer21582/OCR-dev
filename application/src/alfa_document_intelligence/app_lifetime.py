"""Window presence tracking and automatic shutdown of the local server (REQ-101).

The browser windows opened by the launcher send a heartbeat while they are
visible and a "closing" notice when they are closed.  ``WindowPresence`` turns
those signals into a ``should_stop()`` decision; ``AppLifetime`` runs a guard
thread that stops the server when that decision is true or when an explicit
exit was requested.

A window sends "closing" on every ``pagehide``, navigation included.  Both
orders of a navigation are treated as such: a closing that arrives at most
``navigation_window_seconds`` (2 s) after another request, and any other
request that arrives within the closing grace after a closing, keep that window
alive as if it had just sent a heartbeat.  So navigating to a page without the
heartbeat script does not stop the server.  Limit: such a page (for example the
raw view of an original document) keeps the server alive for at most the
heartbeat expiry (180 s) after the navigation; the server then stops unless
another window beats.  A window really closed within 2 s of a request likewise
keeps the server alive for up to 180 s.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import threading
import time
from typing import Callable

_WINDOW_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


def is_valid_window_id(window_id: object) -> bool:
    """Window ids are 1-64 characters from [A-Za-z0-9_-]."""
    return isinstance(window_id, str) and _WINDOW_ID.fullmatch(window_id) is not None


def _check_window_id(window_id: str) -> str:
    if not is_valid_window_id(window_id):
        raise ValueError("invalid window id")
    return window_id


@dataclass(frozen=True)
class AppInfo:
    """What the «Informazioni» page shows about the running program (REQ-106)."""

    version: str
    python_version: str
    ocr_engine: str | None
    runtime_status: str
    instance_id: str = ""


class WindowPresence:
    """Tracks live windows; thread-safe (server thread writes, guard thread reads)."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        *,
        heartbeat_expiry_seconds: float = 180.0,
        closing_grace_seconds: float = 10.0,
        startup_grace_seconds: float = 120.0,
        navigation_window_seconds: float = 2.0,
    ) -> None:
        self._clock = clock
        self._expiry = heartbeat_expiry_seconds
        self._closing_grace = closing_grace_seconds
        self._startup_grace = startup_grace_seconds
        self._navigation_window = navigation_window_seconds
        self._lock = threading.Lock()
        self._started = clock()
        self._last_beat: dict[str, float] = {}
        self._ever_seen = False
        self._last_beat_any = float("-inf")
        self._last_closing: float | None = None
        self._last_activity: float | None = None
        self._pending_closing: dict[str, float] = {}
        self._last_request: float | None = None  # last activity(), not heartbeat/closing

    def heartbeat(self, window_id: str) -> None:
        _check_window_id(window_id)
        with self._lock:
            now = self._clock()
            self._pending_closing.pop(window_id, None)
            self._last_beat[window_id] = now
            self._ever_seen = True
            self._last_beat_any = now
            self._last_activity = now

    def closing(self, window_id: str) -> None:
        _check_window_id(window_id)
        with self._lock:
            now = self._clock()
            if self._last_request is not None and 0 <= now - self._last_request <= self._navigation_window:
                # The next page was requested just before this pagehide: a navigation.
                self._pending_closing.pop(window_id, None)
                self._last_beat[window_id] = now
                self._ever_seen = True
                self._last_beat_any = now
                self._last_activity = now
                return
            self._last_beat.pop(window_id, None)
            self._pending_closing[window_id] = now
            self._last_closing = now
            self._last_activity = now

    def activity(self) -> None:
        """A request other than heartbeat/closing; restores windows closed within the grace."""
        with self._lock:
            now = self._clock()
            self._last_activity = now
            self._last_request = now
            restored = False
            for window_id, closed_at in list(self._pending_closing.items()):
                del self._pending_closing[window_id]
                if 0 <= now - closed_at < self._closing_grace:
                    self._last_beat[window_id] = now
                    restored = True
            if restored:
                self._last_beat_any = now

    def navigation_request(self) -> None:
        """Mark a possible navigation without reviving a closing window."""
        with self._lock:
            self._last_request = self._clock()

    def now(self) -> float:
        return self._clock()

    def resume_after_suspend(self) -> None:
        """Restart grace periods after the guard has been suspended."""
        with self._lock:
            now = self._clock()
            for window_id in self._last_beat:
                self._last_beat[window_id] = now
            for window_id in self._pending_closing:
                self._pending_closing[window_id] = now
            if self._last_closing is not None and self._last_closing >= self._last_beat_any:
                self._last_closing = now
            elif self._ever_seen:
                self._last_beat_any = now
            if self._last_activity is not None:
                self._last_activity = now
            if not self._ever_seen:
                self._started = now

    def should_stop(self) -> bool:
        with self._lock:
            now = self._clock()
            if any(now - beat < self._expiry for beat in self._last_beat.values()):
                return False
            if not self._ever_seen:
                return now - self._started >= self._startup_grace
            if self._last_closing is not None and self._last_closing >= self._last_beat_any:
                # Stale entries are ignored: the last event was an explicit closing: stop after a quiet grace period.
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
        self._suspend_gap = max(30.0, 10 * poll_seconds)
        self._last_poll = presence.now()
        self._exit = threading.Event()
        self._start_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.stopped = threading.Event()

    @property
    def presence(self) -> WindowPresence:
        return self._presence

    def start(self) -> None:
        with self._start_lock:
            if self._thread is not None:
                return
            self._last_poll = self._presence.now()
            self._thread = threading.Thread(target=self._guard, name="ocr2-app-lifetime", daemon=True)
            self._thread.start()

    def request_exit(self) -> None:
        # Never call the server shutdown here: this runs inside a request on the
        # server thread and shutdown() would deadlock.
        self._exit.set()

    def _tick(self) -> bool:
        now = self._presence.now()
        if now - self._last_poll > self._suspend_gap:
            self._presence.resume_after_suspend()
        self._last_poll = now
        return self._presence.should_stop()

    def _guard(self) -> None:
        while not self._exit.wait(self._poll):
            if self._tick():
                break
        try:
            self._stop_server()
        finally:
            self.stopped.set()
