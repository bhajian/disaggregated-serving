"""Arrival processes, goodput, cost, AIPerf export, sweep table and length distributions."""
import asyncio
import json
import random
import statistics
import time
from argparse import Namespace

import httpx
import numpy as np
import pytest

from benchmarks import distributions, loadgen, sweep


def test_poisson_arrivals_are_seeded_and_have_the_requested_rate():
    a = loadgen.arrival_times('poisson', 4.0, 20000, seed=7)
    assert a == loadgen.arrival_times('poisson', 4.0, 20000, seed=7)
    assert a != loadgen.arrival_times('poisson', 4.0, 20000, seed=8)
    gaps = np.diff(a)
    assert abs(gaps.mean() - 0.25) < 0.01                 # mean inter-arrival 1/rps
    assert abs(gaps.std() / gaps.mean() - 1) < 0.05        # exponential: coefficient of variation 1
    assert loadgen.arrival_times('constant', 2.0, 3, 1) == [0.0, 0.5, 1.0]
    assert loadgen.arrival_times('closed', 0, 3, 1) == [0.0, 0.0, 0.0]
    with pytest.raises(ValueError):
        loadgen.arrival_times('poisson', 0, 3, 1)


def row(ttft, itl_p99, n=100, valid=True):
    return {'measurement_valid': valid, 'success': True, 'ttft_ms': ttft, 'itl_ms_p99': itl_p99,
            'completion_tokens': n, 'prompt_tokens': 1000, 'e2e_ms': ttft + n * 10, 'tpot_ms': 10.0}


def test_goodput_counts_only_requests_meeting_both_targets():
    rows = [row(500, 20), row(2500, 20), row(500, 60), row(1900, 39), row(100, 10, valid=False)]
    pooled = np.array([10.0] * 98 + [100.0] * 2, dtype=np.float32)
    g = loadgen.goodput(rows, 10.0, ttft_ms=2000, itl_ms=40, pooled_itl=pooled)
    assert g['slo_requests'] == 2 and g['goodput_rps'] == pytest.approx(0.2)
    assert g['slo_attainment'] == pytest.approx(0.5)       # invalid rows are excluded
    assert g['goodput_output_tps'] == pytest.approx(20.0)
    assert g['run_p99_itl_ms'] > 40 and g['run_meets_slo'] is False


def test_single_token_responses_are_judged_on_ttft_only():
    assert loadgen.request_meets_slo(row(100, None, n=1), 200, 40)
    assert not loadgen.request_meets_slo(row(300, None, n=1), 200, 40)


def test_cost_per_million_tokens():
    c = loadgen.cost(gpu_count=16, gpu_hour_usd=3.0, wall_s=3600, output_tokens=48_000_000, slo_output_tokens=24_000_000)
    assert c['run_cost_usd'] == pytest.approx(48.0)
    assert c['usd_per_m_output_tokens'] == pytest.approx(1.0)
    assert c['usd_per_m_output_tokens_at_slo'] == pytest.approx(2.0)
    assert loadgen.cost(16, 0, 3600, 1, 1)['usd_per_m_output_tokens'] is None   # blank unless priced


def test_aiperf_export_uses_genai_perf_names():
    export = loadgen.aiperf_export([row(500, 20), row(700, 25)], 10.0, np.array([10.0, 12.0]))
    assert {'request_throughput', 'output_token_throughput', 'time_to_first_token', 'inter_token_latency',
            'request_latency', 'output_sequence_length', 'input_sequence_length'} <= set(export)
    assert export['time_to_first_token']['unit'] == 'ms' and export['time_to_first_token']['p50'] == pytest.approx(600)
    assert export['inter_token_latency']['avg'] == pytest.approx(10.0)          # genai-perf ITL = our TPOT
    assert export['inter_token_gap']['max'] == pytest.approx(12.0)


class Stream(httpx.AsyncByteStream):
    def __init__(self, parts): self.parts = parts

    async def __aiter__(self):
        for p in self.parts:
            await asyncio.sleep(0.001)
            yield p


def completion(n):
    chunks = [{'choices': [{'delta': {'content': 'x'}, 'finish_reason': 'length' if i == n - 1 else None}]} for i in range(n)]
    chunks.append({'choices': [], 'usage': {'prompt_tokens': 50, 'completion_tokens': n}})
    return [('data: ' + json.dumps(c) + '\n\n').encode() for c in chunks] + [b'data: [DONE]\n\n']


def test_sessions_run_in_order_with_forced_lengths():
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append((body['messages'][0]['content'], body['max_tokens'], body['ignore_eos']))
        return httpx.Response(200, stream=Stream(completion(body['max_tokens'])))

    a = Namespace(concurrency=0, output_tokens=8, model='m', temperature=0, timeout=10, think_time=0,
                  max_model_len=1000, slo_ttft_ms=5000, slo_itl_ms=1000, base_url='http://test/v1')
    sample = {'id': 's0', 'turns': [{'messages': [{'role': 'user', 'content': 't0'}], 'max_output_tokens': 3},
                                    {'messages': [{'role': 'user', 'content': 't1'}]}]}
    rows, ints = [], []

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await loadgen.run_sessions([(0, 0.0, sample)], a, {}, time.perf_counter(), client, rows, ints)
    asyncio.run(go())
    assert seen == [('t0', 3, True), ('t1', 8, True)]
    assert [r['completion_tokens'] for r in rows] == [3, 8] and all(r['measurement_valid'] and r['slo_met'] for r in rows)
    assert [len(i) for i in ints] == [2, 7]


SPEC = {'study': 's', 'results': 'r', 'dataset': 'd.jsonl', 'model': 'm', 'gpu_count': 16, 'slo': {'ttft_ms': 2000, 'itl_ms': 40},
        'rps': [1, 2], 'loadgen': {'arrival': 'poisson', 'duration': 600, 'metrics_url': ['http://a', 'http://b']},
        'configs': [{'name': 'agg', 'technology': 'dynamo-agg-k8s', 'base_url': 'http://x/v1', 'topology': {'mode': 'agg', 'workers': 4}},
                    {'name': 'pd-1-3', 'technology': 'dynamo-disagg-k8s', 'base_url': 'http://x/v1',
                     'topology': {'mode': 'disagg', 'prefill': 1, 'decode': 3}}]}


def test_sweep_plan_and_loadgen_arguments():
    steps = sweep.plan(SPEC)
    assert [(s['config'], s['rps']) for s in steps] == [('agg', 1), ('agg', 2), ('pd-1-3', 1), ('pd-1-3', 2)]
    args = sweep.loadgen_args(SPEC, steps[3])
    assert args[args.index('--rps') + 1] == '2' and args.count('--metrics-url') == 2
    assert json.loads(args[args.index('--topology') + 1]) == {'mode': 'disagg', 'prefill': 1, 'decode': 3, 'config': 'pd-1-3'}


def test_sweep_table_marks_best_config_at_slo(tmp_path):
    def summary(run, config, rps, good, meets):
        d = tmp_path / run; d.mkdir()
        (d / 'summary.json').write_text(json.dumps({'run_id': run, 'topo_config': config, 'offered_rps': rps,
                                                    'goodput_rps': good, 'run_meets_slo': meets}))
    summary('a1', 'agg', 1, 0.9, True); summary('a2', 'agg', 2, 1.7, True); summary('a3', 'agg', 4, 1.0, False)
    summary('p1', 'pd', 1, 0.95, True); summary('p2', 'pd', 2, 1.9, True)
    out, rows = sweep.table(tmp_path)
    best = {(r['config'], r['offered_rps']) for r in rows if r['best_at_slo']}
    assert best == {('agg', 2), ('pd', 2)} and out.exists()


def test_length_distributions_are_bounded_and_independent():
    s = distributions.sampler(distributions.DEFAULT_ISL, seed=1, stream='isl')
    values = [s() for _ in range(5000)]
    assert min(values) >= 2000 and max(values) <= 16000
    assert 3500 < statistics.median(values) < 4500
    again = distributions.sampler(distributions.DEFAULT_ISL, seed=1, stream='isl')
    assert [again() for _ in range(10)] == values[:10]    # reproducible per (seed, stream)
    a, b = distributions.sampler('uniform:1:100', 1, 'x'), distributions.sampler('uniform:1:100', 1, 'y')
    assert [a() for _ in range(20)] != [b() for _ in range(20)]
    assert distributions.sample('fixed:256', random.Random(0)) == 256
    with pytest.raises(ValueError):
        distributions.parse('normal:1:2')
