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


def test_activity_after_the_grace_only_extends_the_quiet_period():
    clock, presence = _presence()
    presence.heartbeat("w1")
    presence.closing("w1")
    clock.advance(10)
    presence.activity()
    clock.advance(8)
    assert presence.should_stop() is False
    clock.advance(3)
    assert presence.should_stop() is True


def test_request_after_closing_restores_window():
    clock, presence = _presence()
    presence.heartbeat("w")
    presence.closing("w")
    clock.advance(1)
    presence.activity()
    clock.advance(20)
    assert presence.should_stop() is False
    clock.advance(170)
    assert presence.should_stop() is True


def test_closing_beacon_alone_still_stops_after_grace():
    clock, presence = _presence()
    presence.heartbeat("w")
    presence.closing("w")
    clock.advance(9)
    assert presence.should_stop() is False
    clock.advance(1)
    assert presence.should_stop() is True


def test_closing_right_after_a_request_counts_as_navigation():
    clock, presence = _presence()
    presence.heartbeat("w")
    clock.advance(50)
    presence.activity()
    clock.advance(1)
    presence.closing("w")
    clock.advance(29)
    assert presence.should_stop() is False
    clock.advance(180 + 1 - 29)
    assert presence.should_stop() is True


def test_closing_long_after_a_request_still_stops():
    clock, presence = _presence()
    presence.heartbeat("w")
    clock.advance(50)
    presence.activity()
    clock.advance(5)
    presence.closing("w")
    clock.advance(9)
    assert presence.should_stop() is False
    clock.advance(2)
    assert presence.should_stop() is True


def test_heartbeat_clears_pending_closing():
    clock, presence = _presence()
    presence.heartbeat("w")
    presence.closing("w")
    clock.advance(1)
    presence.heartbeat("w")
    presence.closing("w")
    clock.advance(10)
    presence.activity()  # the first closing is no longer pending and the second is past the grace
    clock.advance(10)
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
    # Time passes in steps shorter than the suspend gap (R40): a real expiry, not a sleep.
    for _ in range(50):
        clock.advance(10)
        if lifetime.stopped.wait(0.05):
            break
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


def test_stale_window_does_not_skip_closing_grace():
    clock, presence = _presence()
    presence.heartbeat("w1")
    clock.advance(100)
    presence.heartbeat("w2")
    clock.advance(100)  # w1 is dead, w2 still alive
    presence.heartbeat("w2")
    presence.closing("w2")
    clock.advance(2)
    assert presence.should_stop() is False
    clock.advance(9)
    assert presence.should_stop() is True


def test_all_windows_silent_without_closing_stop_at_expiry():
    clock, presence = _presence()
    presence.heartbeat("w1")
    presence.heartbeat("w2")
    presence.closing("w2")
    presence.heartbeat("w2")
    clock.advance(179)
    assert presence.should_stop() is False
    clock.advance(2)
    assert presence.should_stop() is True


# --- R40: a suspend (sleep/hibernation) does not stop the server -------------


def _lifetime(clock, presence, poll_seconds=1.0):
    calls = []
    return calls, AppLifetime(presence, lambda: calls.append(1), poll_seconds=poll_seconds)


def test_guard_tick_treats_a_long_poll_gap_as_a_suspend():
    clock, presence = _presence()
    calls, lifetime = _lifetime(clock, presence)
    presence.heartbeat("w1")
    clock.advance(1)
    assert lifetime._tick() is False
    clock.advance(300)  # the PC slept 5 minutes; the monotonic clock kept counting
    assert lifetime._tick() is False, "a suspend must not stop the server"
    for _ in range(17):  # one more expiry period from the wake-up
        clock.advance(10)
        assert lifetime._tick() is False
    clock.advance(11)
    assert lifetime._tick() is True  # no heartbeat after the wake-up: the window is gone
    assert calls == []  # _tick only decides; the guard thread stops the server


def test_guard_tick_without_a_gap_still_expires_silent_windows():
    clock, presence = _presence()
    _calls, lifetime = _lifetime(clock, presence)
    presence.heartbeat("w1")
    for _ in range(17):
        clock.advance(10)
        assert lifetime._tick() is False
    clock.advance(11)
    assert lifetime._tick() is True


def test_suspend_gap_threshold_is_at_least_thirty_seconds_and_ten_polls():
    clock, presence = _presence()
    _calls, short = _lifetime(clock, presence, poll_seconds=1.0)
    _calls, long = _lifetime(clock, presence, poll_seconds=5.0)
    assert short._suspend_gap == 30.0 and long._suspend_gap == 50.0


def test_suspend_moves_a_pending_closing_and_the_startup_grace_forward():
    clock, presence = _presence()
    _calls, lifetime = _lifetime(clock, presence)
    lifetime._tick()
    clock.advance(100)
    presence.resume_after_suspend()
    clock.advance(119)
    assert presence.should_stop() is False  # startup grace counted again from the wake-up
    presence.heartbeat("w1")
    presence.closing("w1")
    clock.advance(400)
    presence.resume_after_suspend()
    clock.advance(9)
    assert presence.should_stop() is False
    clock.advance(2)
    assert presence.should_stop() is True


def test_guard_thread_survives_a_suspend():
    clock, presence = _presence()
    presence.heartbeat("w1")
    calls, lifetime = _lifetime(clock, presence, poll_seconds=0.01)
    lifetime.start()
    try:
        assert not lifetime.stopped.wait(0.1)
        clock.advance(300)
        assert not lifetime.stopped.wait(0.3), "the guard stopped the server after a suspend"
    finally:
        lifetime.request_exit()
    assert lifetime.stopped.wait(2.0)


# --- R41: a window restored by navigation gets the 30-minute session idle time ---


def _navigation_presence():
    clock = _Clock()
    return clock, WindowPresence(clock, navigation_expiry_seconds=1800.0)


def test_closing_right_after_a_request_keeps_the_window_for_the_session_idle_time():
    clock, presence = _navigation_presence()
    presence.heartbeat("w")
    clock.advance(50)
    presence.activity()  # «Apri documento originale»: a page without the heartbeat script
    clock.advance(1)
    presence.closing("w")
    clock.advance(1799)
    assert presence.should_stop() is False
    clock.advance(2)
    assert presence.should_stop() is True


def test_request_after_closing_keeps_the_window_for_the_session_idle_time():
    clock, presence = _navigation_presence()
    presence.heartbeat("w")
    presence.closing("w")
    clock.advance(1)
    presence.activity()
    clock.advance(1799)
    assert presence.should_stop() is False
    clock.advance(1)
    assert presence.should_stop() is True


def test_next_heartbeat_brings_a_restored_window_back_to_the_normal_expiry():
    clock, presence = _navigation_presence()
    presence.heartbeat("w")
    presence.activity()
    clock.advance(1)
    presence.closing("w")
    clock.advance(600)
    presence.heartbeat("w")  # back on a page with the heartbeat script
    clock.advance(179)
    assert presence.should_stop() is False
    clock.advance(2)
    assert presence.should_stop() is True


def test_navigation_expiry_defaults_to_the_heartbeat_expiry():
    clock, presence = _presence()
    presence.heartbeat("w")
    presence.activity()
    clock.advance(1)
    presence.closing("w")
    clock.advance(181)
    assert presence.should_stop() is True
