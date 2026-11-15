"""Window presence tracking and automatic shutdown guard (REQ-101)."""
from __future__ import annotations

import threading

import pytest

from alfa_document_intelligence.app_lifetime import AppLifetime, WindowPresence


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _presence():
    clock = _Clock()
    return clock, WindowPresence(clock)


def test_no_window_ever_stops_after_startup_grace():
    clock, presence = _presence()
    clock.advance(119)
    assert presence.should_stop() is False
    clock.advance(2)
    assert presence.should_stop() is True


def test_activity_alone_does_not_count_as_a_window():
    clock, presence = _presence()
    clock.advance(100)
    presence.activity()
    clock.advance(30)
    assert presence.should_stop() is True


def test_live_window_keeps_server_alive_with_heartbeats():
    clock, presence = _presence()
    for _ in range(10):
        presence.heartbeat("w1")
        clock.advance(60)
        assert presence.should_stop() is False


def test_closing_last_window_stops_after_ten_seconds():
    clock, presence = _presence()
    presence.heartbeat("w1")
    clock.advance(5)
    presence.closing("w1")
    clock.advance(9)
    assert presence.should_stop() is False
    clock.advance(2)
    assert presence.should_stop() is True


def test_activity_after_closing_extends_the_grace():
    clock, presence = _presence()
    presence.heartbeat("w1")
    presence.closing("w1")
    clock.advance(8)
    presence.activity()
    clock.advance(8)
    assert presence.should_stop() is False
    clock.advance(3)
    assert presence.should_stop() is True


def test_navigation_within_window_does_not_stop():
    clock, presence = _presence()
    presence.heartbeat("w1")
    clock.advance(30)
    presence.closing("w1")
    clock.advance(2)
    presence.heartbeat("w1")
    for _ in range(5):
        clock.advance(60)
        assert presence.should_stop() is False
        presence.heartbeat("w1")


def test_second_window_keeps_server_alive_when_first_closes():
    clock, presence = _presence()
    presence.heartbeat("w1")
    presence.heartbeat("w2")
    presence.closing("w1")
    clock.advance(10)
    assert presence.should_stop() is False
    clock.advance(60)
    presence.heartbeat("w2")
    assert presence.should_stop() is False
    clock.advance(60)
    presence.heartbeat("w2")
    assert presence.should_stop() is False


def test_silent_window_expires_after_180_seconds():
    clock, presence = _presence()
    presence.heartbeat("w1")
    clock.advance(179)
    assert presence.should_stop() is False
    clock.advance(2)
    assert presence.should_stop() is True


@pytest.mark.parametrize("bad", ["", "a" * 65, "a b", "a/b", "é", "a.b"])
def test_invalid_window_id_is_rejected(bad):
    _, presence = _presence()
    with pytest.raises(ValueError):
        presence.heartbeat(bad)
    with pytest.raises(ValueError):
        presence.closing(bad)


def test_valid_window_id_boundaries_are_accepted():
    _, presence = _presence()
    presence.heartbeat("a")
    presence.heartbeat("A_z-9" * 12 + "abcd")


def test_request_exit_stops_once():
    _, presence = _presence()
    calls = []
    lifetime = AppLifetime(presence, lambda: calls.append(1), poll_seconds=0.01)
    lifetime.start()
    lifetime.request_exit()
    lifetime.request_exit()
    assert lifetime.stopped.wait(2.0)
    assert calls == [1]


def test_guard_thread_stops_server_when_presence_says_so():
    clock, presence = _presence()
    calls = []
    lifetime = AppLifetime(presence, lambda: calls.append(1), poll_seconds=0.01)
    lifetime.start()
    assert not lifetime.stopped.wait(0.1)
    clock.advance(500)
    assert lifetime.stopped.wait(2.0)
    assert calls == [1]


def test_request_exit_does_not_call_stop_in_caller_thread():
    _, presence = _presence()
    threads = []
    lifetime = AppLifetime(presence, lambda: threads.append(threading.current_thread()), poll_seconds=0.01)
    lifetime.start()
    lifetime.request_exit()
    assert lifetime.stopped.wait(2.0)
    assert threads and threads[0] is not threading.main_thread()
