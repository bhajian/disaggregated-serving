import pytest
from benchmarks.metrics import request_metrics, summarize, percentile


def test_exact_itl_and_distinct_throughput_definitions():
    events = [{'time_s': t, 'token_count': 1} for t in [1, 1.1, 1.3]]
    r = request_metrics(events, 1.5, 3)
    assert r['ttft_ms'] == 1000
    assert r['tpot_ms'] == pytest.approx(150)
    assert r['output_tps'] == 2
    assert r['decode_tps'] == pytest.approx(2 / .3)
    assert r['itl_ms'] == pytest.approx([100, 200])


@pytest.mark.parametrize('counts,total', [([2, 1], 3), ([None, None], 2), ([1, 1], 3)])
def test_no_fabricated_token_timestamps(counts, total):
    r = request_metrics([{'time_s': i + 1, 'token_count': n} for i, n in enumerate(counts)], 3, total)
    assert r['itl_available'] is False
    assert r['itl_ms'] == []
    assert r['chunk_intervals_ms'] == [1000]


def test_single_token_and_no_output():
    assert request_metrics([{'time_s': 1, 'token_count': 1}], 2, 1)['tpot_ms'] is None
    assert request_metrics([], 2, None)['ttft_ms'] is None
    assert percentile([], 99) is None


def test_failures_in_wall_time_but_not_success_token_totals():
    metric = request_metrics([{'time_s': 1, 'token_count': 1}], 2, 1)
    good = dict(metric, success=True, measurement_valid=True, prompt_tokens=256000, completion_tokens=1)
    failed = dict(good, success=False, completion_tokens=100)
    invalid = dict(good, measurement_valid=False, completion_tokens=200)
    summary = summarize([good, failed, invalid], 10)
    assert summary['output_throughput_tps'] == .1
    assert summary['failed_requests'] == 1
    assert summary['invalid_measurements'] == 1
    assert summary['error_rate'] == pytest.approx(1 / 3)
