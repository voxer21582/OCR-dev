import threading

import pytest

from tools import measure_case_load as load
from tools.measure_case_load import summarize_route


def test_route_summary_reports_errors_separately_from_latency():
    result = summarize_route([(200, 10.0), (500, 900.0), (200, 30.0), (200, 20.0)])
    assert result == {
        'samples': 4, 'http_200': 3, 'other_statuses': {'500': 1},
        'p95_ms': 30.0, 'max_ms': 30.0,
    }


def test_route_summary_does_not_invent_latency_without_successes():
    result = summarize_route([(500, 2.0)])
    assert result['http_200'] == 0
    assert result['p95_ms'] is None and result['max_ms'] is None


@pytest.mark.parametrize('fail', [False, True])
def test_load_collection_stops_and_restores_client(monkeypatch, tmp_path, fail):
    sampled = threading.Event()

    def request(self, method, path, *args, **kwargs):
        if path in {'/', '/cases'}:
            sampled.set()
            return 200, b'synthetic page'
        return 200, b'Elaborazione locale in corso'

    def run(fixtures, work_dir, *, python, observe_network):
        assert observe_network is False
        client = load.bench._Client(8080)
        client.request('GET', '/cases/test/jobs/synthetic')
        assert sampled.wait(3)
        if fail:
            raise load.bench.BenchmarkError('synthetic failure')
        return {'pages_processed': 1, 'ocr_seconds': 1.0}

    monkeypatch.setattr(load.bench._Client, 'request', request)
    monkeypatch.setattr(load.bench, 'run_case_benchmark', run)
    if fail:
        with pytest.raises(load.bench.BenchmarkError, match='synthetic'):
            load.measure(tmp_path, tmp_path, python='synthetic')
    else:
        result = load.measure(tmp_path, tmp_path, python='synthetic')
        assert result['routes']['/']['http_200'] >= 1
    assert load.bench._Client.request is request
