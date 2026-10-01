import asyncio
import csv
import json
import time

import httpx
import numpy as np
import pytest

from benchmarks.long_decode import (derived_tables, histogram_quantile, histograms, server_histograms,
                                    stream_request, summarize, validate)


class Stream(httpx.AsyncByteStream):
    def __init__(self, parts):
        self.parts = parts

    async def __aiter__(self):
        for part in self.parts:
            await asyncio.sleep(.002)
            yield part


def body(tokens, empty_at=None, usage_tokens=None):
    chunks = [{'choices': [{'delta': {'role': 'assistant', 'content': 'a' if i != empty_at else ''},
                            'finish_reason': 'length' if i == tokens - 1 else None}],
               **({'nvext': {'worker_id': {'prefill_worker_id': 1, 'decode_worker_id': 2}}} if i == 0 else {})}
              for i in range(tokens)]
    chunks.append({'choices': [], 'usage': {'prompt_tokens': 8000,
                                            'completion_tokens': usage_tokens or tokens}})
    data = ''.join('data: ' + json.dumps(x) + '\n\n' for x in chunks) + 'data: [DONE]\n\n'
    return [(p + '\n\n').encode() for p in data.split('\n\n') if p]


@pytest.mark.asyncio
async def test_empty_delta_chunks_count_as_token_events():
    transport = httpx.MockTransport(lambda _: httpx.Response(200, stream=Stream(body(5, empty_at=2))))
    async with httpx.AsyncClient(transport=transport) as client:
        row, intervals = await stream_request(client, 'http://test/v1', {}, 5, time.perf_counter())
    assert row['success'] and row['stream_events'] == 5 and row['content_events'] == 4
    assert len(intervals) == 4 and row['itl_token_coverage'] == 1
    assert row['decode_worker_id'] == 2 and row['tpot_ms'] > 0
    validate(row, 5, 7000, 262144)
    assert row['measurement_valid']


@pytest.mark.asyncio
async def test_short_completion_is_invalid():
    transport = httpx.MockTransport(lambda _: httpx.Response(200, stream=Stream(body(3))))
    async with httpx.AsyncClient(transport=transport) as client:
        row, _ = await stream_request(client, 'http://test/v1', {}, 5, time.perf_counter())
    validate(row, 131072, 0, 262144)
    assert row['success'] and not row['measurement_valid']
    assert 'forced_length' in row['measurement_issue']


PROM = '''# TYPE sglang:inter_token_latency_seconds histogram
sglang:inter_token_latency_seconds_sum{{worker_id="a"}} {s}
sglang:inter_token_latency_seconds_bucket{{le="0.01",worker_id="a"}} {a}
sglang:inter_token_latency_seconds_bucket{{le="0.02",worker_id="a"}} {b}
sglang:inter_token_latency_seconds_bucket{{le="+Inf",worker_id="a"}} {b}
sglang:inter_token_latency_seconds_count{{worker_id="a"}} {b}
'''


def test_histogram_delta_and_quantile(tmp_path):
    (tmp_path / 'metrics-before-0.prom').write_text(PROM.format(s=1, a=100, b=100))
    (tmp_path / 'metrics-after-0.prom').write_text(PROM.format(s=4, a=200, b=300))
    h = histograms((tmp_path / 'metrics-after-0.prom').read_text())['sglang:inter_token_latency_seconds']
    assert h['count'] == 300 and h['buckets'][0.02] == 300
    s = server_histograms(tmp_path, 1)
    # Delta: 100 samples <= 10 ms and 100 in (10, 20] ms.
    assert s['server_itl_ms_count'] == 200 and s['server_itl_ms_mean'] == pytest.approx(15)
    assert s['server_itl_ms_p50'] == pytest.approx(10)
    assert s['server_itl_ms_p99'] == pytest.approx(19.8)
    assert histogram_quantile({}, .5) is None


def test_derived_tables_and_steady_window(tmp_path):
    rows = []
    with (tmp_path / 'intervals-00.f32').open('wb') as f:
        for i in range(2):
            values = np.full(2047, 10.0 + i, dtype=np.float32)
            values.tofile(f)
            rows.append({'success': True, 'measurement_valid': True, 'completion_tokens': 2048,
                         'prompt_tokens': 8000, 'stream_events': 2048, 'first_token_s': 1.0 + i,
                         'last_token_s': 1.0 + i + values.sum() / 1000, 'intervals_file': 'intervals-00.f32',
                         'intervals_offset': i * 2047, 'intervals_count': 2047, 'ttft_ms': 1000.0,
                         'tpot_ms': 10.0 + i, 'itl_token_coverage': 1.0})
    pooled = derived_tables(tmp_path, rows, 30)
    assert len(pooled) == 4094
    with (tmp_path / 'itl_by_position.csv').open() as f:
        table = list(csv.DictReader(f))
    assert [int(r['samples']) for r in table] == [2046, 2048]
    with (tmp_path / 'throughput_timeline.csv').open() as f:
        assert sum(int(r['stream_events']) for r in csv.DictReader(f)) == 4096
    s = summarize(rows, 30, pooled)
    assert s['itl_token_coverage'] == 1 and s['itl_coverage'] == 1
    assert s['itl_ms_p50'] == pytest.approx(10.5, abs=.5)
    assert s['steady_window_s'] == pytest.approx(1.0 + 20.47 - 2.0, rel=1e-3)
    assert s['steady_decode_tps'] > 0
