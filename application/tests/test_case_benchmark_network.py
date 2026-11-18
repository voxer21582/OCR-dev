from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from tools.run_case_benchmark import BenchmarkError, _HOOK, _network_summary, _page_interval_summary


def test_hook_does_not_report_ready_when_installation_fails(tmp_path, monkeypatch):
    log = tmp_path / 'network.log'
    monkeypatch.setenv('OCR2_BENCHMARK_NET_LOG', str(log))
    monkeypatch.setitem(sys.modules, 'socket', SimpleNamespace(socket=object()))
    with pytest.raises(AttributeError):
        exec(_HOOK, {})
    assert not log.exists()


def test_network_summary_requires_evidence_hook_was_loaded(tmp_path):
    log = tmp_path / 'network.log'
    log.write_text('', encoding='ascii')
    with pytest.raises(BenchmarkError, match='hook'):
        _network_summary(log)


def test_network_summary_counts_only_known_events(tmp_path):
    log = tmp_path / 'network.log'
    log.write_text('ready\nready\nconnect\ndns\n', encoding='ascii')
    assert _network_summary(log) == {
        'python_hook_initializations': 2,
        'network_observation_scope': 'partial: instrumented Python processes only; worker and native coverage unverified',
        'non_loopback_connect_attempts': 1,
        'non_loopback_dns_attempts': 1,
    }
    log.write_text('ready\nunexpected\n', encoding='ascii')
    with pytest.raises(BenchmarkError, match='event'):
        _network_summary(log)


def test_page_intervals_exclude_jumps_and_report_regressions():
    result = _page_interval_summary([(0.0, 0), (1.0, 1), (4.0, 2), (5.0, 4), (6.0, 3)])
    assert result == {
        'sampled_page_intervals': 2, 'page_interval_median_seconds': 2.0,
        'page_interval_max_seconds': 3.0, 'page_progress_jumps': 1,
        'page_progress_regressions': 1,
    }


def test_page_intervals_without_contiguous_progress_are_unknown():
    result = _page_interval_summary([(0.0, 0), (1.0, 2)])
    assert result['sampled_page_intervals'] == 0
    assert result['page_interval_median_seconds'] is None


def test_extended_observer_records_only_event_types_and_process_id(tmp_path, monkeypatch):
    from types import ModuleType
    log = tmp_path / 'network.log'
    monkeypatch.setenv('OCR2_BENCHMARK_NET_LOG', str(log))

    class FakeSocket:
        def connect(self, address): return 'connected'
        def connect_ex(self, address): return 0
        def sendto(self, data, address): return len(data)

    fake = ModuleType('socket')
    fake.socket = FakeSocket
    fake.getaddrinfo = lambda *args, **kwargs: []
    monkeypatch.setitem(sys.modules, 'socket', fake)
    source = Path(__file__).parents[1] / 'tools' / 'network_observer_hook.py'
    exec(compile(source.read_text(encoding='utf-8'), str(source), 'exec'), {})
    sock = FakeSocket()
    sock.connect(('127.0.0.1', 80))
    sock.connect(('198.51.100.4', 80))
    sock.connect_ex(('198.51.100.5', 80))
    sock.sendto(b'x', ('198.51.100.6', 53))
    fake.getaddrinfo('example.invalid', 80)
    rows = [line.split() for line in log.read_text(encoding='ascii').splitlines()]
    assert [row[0] for row in rows] == ['ready', 'connect', 'connect_ex', 'sendto', 'dns']
    assert all(len(row) == 2 and row[1].isdigit() for row in rows)
    assert '198.51.100' not in log.read_text(encoding='ascii')
