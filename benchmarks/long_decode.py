#!/usr/bin/env python3
"""Benchmark forced long generations (for example 8K in, 128K out) at high concurrency.

benchmarks.run keeps every streamed chunk in memory and parses all streams in
one process. That is fine for a few hundred output tokens, but not for hundreds
of concurrent 128K-token streams: parsing would fall behind the server and
inflate the very intervals being measured. This runner instead:

- splits the streams across client processes that share one CLOCK_MONOTONIC
  start time, so all timestamps are directly comparable;
- keeps one float32 interval per stream event, written to binary files;
- forces exact output lengths (ignore_eos) and rejects shorter completions;
- derives ITL from stream-event intervals and reports how many tokens arrived
  in their own event (coverage), plus the server-side SGLang ITL histogram.

Output folders match benchmarks.run (summary.csv/json, requests.csv,
metadata.json, metrics-*.prom), so benchmarks.collect still works.
"""
import argparse
import array
import asyncio
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import platform
import re
import sys
import time
import uuid

import httpx
import numpy as np

try:
    import orjson
    loads = orjson.loads
except ImportError:  # Local analysis does not need the fast parser.
    loads = json.loads

from benchmarks.metrics import distribution
from benchmarks.run import load_sessions, snapshot_metrics, sse_events, write_csv

POSITION_BIN = 1024  # Output tokens per bin for ITL-versus-position tables.
TIMELINE_BIN_S = 10
STALL_MS = (50, 100, 1000)  # Decode stalls, for example a co-scheduled prefill.


async def stream_request(client, url, body, timeout, run_start):
    """Stream one request; return scalars plus per-event intervals in ms."""
    start = time.perf_counter()
    intervals = array.array('f')
    usage, worker = {}, None
    first = last = None
    choice_events = content_events = 0
    finish_reason, error, done, status = None, '', False, None
    try:
        async with asyncio.timeout(timeout):
            async with client.stream('POST', url.rstrip('/') + '/chat/completions', json=body) as response:
                status = response.status_code
                if status != 200:
                    await response.aread()
                    raise RuntimeError(f'HTTP {status}: {response.text[:1000]}')
                async for data in sse_events(response):
                    now = time.perf_counter()
                    if data.strip() == '[DONE]':
                        done = True
                        break
                    obj = loads(data)
                    if obj.get('error'):
                        raise RuntimeError(str(obj['error']))
                    if obj.get('usage'):
                        usage = obj['usage']
                    if worker is None and obj.get('nvext', {}).get('worker_id'):
                        worker = obj['nvext']['worker_id']
                    choices = obj.get('choices') or []
                    if not choices:
                        continue
                    choice = choices[0]
                    delta = choice.get('delta') or {}
                    # Each engine step emits one chunk. A chunk can be empty when
                    # the detokenizer holds back a partial character or a
                    # skipped special token, so count every chunk carrying a
                    # delta, not only visible text.
                    if delta or choice.get('finish_reason'):
                        if delta.get('content') or delta.get('reasoning_content'):
                            content_events += 1
                        if first is None:
                            first = now
                        else:
                            intervals.append((now - last) * 1000)
                        last = now
                        choice_events += 1
                    if choice.get('finish_reason'):
                        finish_reason = choice['finish_reason']
                        if finish_reason == 'error':
                            raise RuntimeError('Server sent finish_reason=error')
        if not done:
            raise RuntimeError('Stream ended without [DONE]')
        if finish_reason is None:
            raise RuntimeError('Stream ended without finish_reason')
        if first is None:
            raise RuntimeError('Stream returned no generated output')
    except (httpx.HTTPError, RuntimeError, ValueError, TimeoutError) as exc:
        error = f'{type(exc).__name__}: {exc}'
    end = time.perf_counter()
    n, prompt = usage.get('completion_tokens'), usage.get('prompt_tokens')
    row = {'success': not error, 'error': error, 'http_status': status,
           'prompt_tokens': prompt, 'completion_tokens': n,
           'cached_tokens': (usage.get('prompt_tokens_details') or {}).get('cached_tokens'),
           'finish_reason': finish_reason,
           'start_s': start - run_start, 'end_s': end - run_start,
           'first_token_s': first - run_start if first else None,
           'last_token_s': last - run_start if last else None,
           'ttft_ms': (first - start) * 1000 if first else None,
           'e2e_ms': (end - start) * 1000,
           'tpot_ms': (last - first) * 1000 / (n - 1) if first and isinstance(n, int) and n > 1 else None,
           'output_tps': n / (end - start) if isinstance(n, int) else None,
           'decode_tps': (n - 1) / (last - first) if first and last > first and isinstance(n, int) else None,
           'stream_events': choice_events, 'content_events': content_events,
           'itl_token_coverage': choice_events / n if isinstance(n, int) and n else None,
           'prefill_worker_id': (worker or {}).get('prefill_worker_id'),
           'decode_worker_id': (worker or {}).get('decode_worker_id')}
    if intervals:
        values = np.frombuffer(intervals, dtype=np.float32)
        row.update({f'itl_ms_p{p}': float(np.percentile(values, p)) for p in (50, 90, 99)},
                   itl_ms_mean=float(values.mean()), itl_ms_max=float(values.max()))
    return row, intervals


def validate(row, output_tokens, min_input, max_context):
    issues = []
    n, prompt = row['completion_tokens'], row['prompt_tokens']
    if not isinstance(prompt, int) or not isinstance(n, int) or n < 1:
        issues.append('missing_or_invalid_server_usage')
    else:
        if n != output_tokens:
            issues.append('completion_tokens_differ_from_forced_length')
        if prompt < min_input:
            issues.append('input_below_requested_minimum')
        if prompt + output_tokens > max_context:
            issues.append('input_plus_reserved_output_exceeds_context')
    row['measurement_valid'] = row['success'] and not issues
    row['measurement_issue'] = ';'.join(issues)


def client_process(index, jobs, a, extra, out, run_start_at):
    """One client process: closed loop over its share of sessions."""
    async def main():
        limit = len(jobs) if not a.concurrency else max(1, a.concurrency // a.processes +
                                                         (index < a.concurrency % a.processes))
        limits = httpx.Limits(max_connections=limit + 4, max_keepalive_connections=limit)
        intervals_file = (out / f'intervals-{index:02d}.f32').open('wb')
        rows_file = (out / f'rows-{index:02d}.jsonl').open('w')
        offset = 0
        async with httpx.AsyncClient(limits=limits, timeout=httpx.Timeout(a.timeout, connect=30)) as client:
            await asyncio.sleep(max(0, run_start_at - time.perf_counter()))
            sem = asyncio.Semaphore(limit)

            async def one(job):
                nonlocal offset
                session_index, sample = job
                turn = sample['turns'][0]
                body = {'model': a.model, 'messages': turn['messages'], 'max_tokens': a.output_tokens,
                        'temperature': a.temperature, 'stream': True, 'ignore_eos': True,
                        'stream_options': {'include_usage': True},
                        'nvext': {'extra_fields': ['worker_id']}, **extra}
                async with sem:
                    queued = time.perf_counter() - run_start_at
                    row, intervals = await stream_request(client, a.base_url, body, a.timeout, run_start_at)
                validate(row, a.output_tokens, a.min_input_tokens, a.max_model_len)
                intervals.tofile(intervals_file)
                row.update(session_id=sample['id'], session_index=session_index, client_process=index,
                           client_queue_ms=queued * 1000, planned_input_tokens=turn.get('input_tokens'),
                           intervals_file=intervals_file.name.rsplit('/', 1)[-1],
                           intervals_offset=offset, intervals_count=len(intervals),
                           request_sha256=hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest())
                offset += len(intervals)
                rows_file.write(json.dumps(row) + '\n'); rows_file.flush()
                print(f'p{index} {sample["id"]}: success={row["success"]} valid={row["measurement_valid"]} '
                      f'TTFT={row["ttft_ms"]:.0f}ms tokens={row["completion_tokens"]} '
                      f'TPOT={row["tpot_ms"] or float("nan"):.2f}ms coverage={row["itl_token_coverage"]}',
                      flush=True)

            await asyncio.gather(*(one(job) for job in jobs))
        intervals_file.close(); rows_file.close()
    asyncio.run(main())


HIST = re.compile(r'^(sglang:(?:inter_token_latency|time_to_first_token|e2e_request_latency)_seconds)'
                  r'_(bucket|count|sum)\{(.*)\}\s+([0-9.eE+-]+|NaN)$')


def histograms(text):
    """Sum histogram series across label sets, keyed by metric and bucket bound."""
    result = {}
    for line in text.splitlines():
        m = HIST.match(line)
        if not m:
            continue
        name, kind, labels, value = m.groups()
        h = result.setdefault(name, {'buckets': {}, 'count': 0.0, 'sum': 0.0})
        if kind == 'bucket':
            le = re.search(r'le="([^"]+)"', labels).group(1)
            bound = math.inf if le == '+Inf' else float(le)
            h['buckets'][bound] = h['buckets'].get(bound, 0.0) + float(value)
        else:
            h[kind] += float(value)
    return result


def histogram_quantile(buckets, q):
    """Prometheus-style linear interpolation over cumulative bucket counts."""
    bounds = sorted(buckets)
    total = buckets[bounds[-1]] if bounds else 0
    if total <= 0:
        return None
    rank, prev_bound, prev_count = q * total, 0.0, 0.0
    for bound in bounds:
        count = buckets[bound]
        if count >= rank:
            if math.isinf(bound):
                return prev_bound
            width = count - prev_count
            return prev_bound + (bound - prev_bound) * ((rank - prev_count) / width if width else 0)
        prev_bound, prev_count = bound, count
    return prev_bound


def server_histograms(out, files):
    """Per-run histogram deltas (after minus before), summed across workers."""
    summary = {}
    total = {}
    for i in range(files):
        before, after = out / f'metrics-before-{i}.prom', out / f'metrics-after-{i}.prom'
        if not (before.exists() and after.exists()):
            return {'server_histograms_complete': False}
        b, e = histograms(before.read_text()), histograms(after.read_text())
        for name, h in e.items():
            t = total.setdefault(name, {'buckets': {}, 'count': 0.0, 'sum': 0.0})
            old = b.get(name, {'buckets': {}, 'count': 0.0, 'sum': 0.0})
            for bound, value in h['buckets'].items():
                t['buckets'][bound] = t['buckets'].get(bound, 0.0) + value - old['buckets'].get(bound, 0.0)
            t['count'] += h['count'] - old['count']; t['sum'] += h['sum'] - old['sum']
    short = {'sglang:inter_token_latency_seconds': 'server_itl_ms',
             'sglang:time_to_first_token_seconds': 'server_ttft_ms',
             'sglang:e2e_request_latency_seconds': 'server_e2e_ms'}
    for name, h in total.items():
        key = short[name]
        summary[key + '_count'] = h['count']
        summary[key + '_mean'] = h['sum'] / h['count'] * 1000 if h['count'] else None
        for q in (50, 90, 99):
            v = histogram_quantile(h['buckets'], q / 100)
            summary[f'{key}_p{q}'] = v * 1000 if v is not None else None
    summary['server_histograms_complete'] = True
    return summary


def load_intervals(out, rows):
    """Return per-row float32 interval arrays from the client binary files."""
    cache = {}
    for row in rows:
        name = row['intervals_file']
        if name not in cache:
            cache[name] = np.fromfile(out / name, dtype=np.float32)
        yield row, cache[name][row['intervals_offset']:row['intervals_offset'] + row['intervals_count']]


def derived_tables(out, rows, wall_s):
    """ITL by output position and cluster output rate over time."""
    valid = [r for r in rows if r['measurement_valid']]
    bins = {}
    timeline = np.zeros(int(math.ceil(wall_s / TIMELINE_BIN_S)) + 1)
    pooled = []
    for row, values in load_intervals(out, valid):
        pooled.append(values)
        # Event k (k >= 1) arrives after interval k-1; event 0 is the first token.
        times = row['first_token_s'] + np.concatenate([[0.0], np.cumsum(values, dtype=np.float64) / 1000])
        np.add.at(timeline, (times // TIMELINE_BIN_S).astype(int).clip(0, len(timeline) - 1), 1)
        # Interval k precedes event k + 1; bin events by their index in the output.
        for b in range(len(values) // POSITION_BIN + 1):
            chunk = values[max(0, b * POSITION_BIN - 1):(b + 1) * POSITION_BIN - 1]
            if len(chunk):
                bins.setdefault(b, []).append(chunk)
    with (out / 'itl_by_position.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['output_token_start', 'output_token_end', 'samples', 'itl_ms_mean', 'itl_ms_p50',
                    'itl_ms_p90', 'itl_ms_p99', 'itl_ms_max'])
        for b in sorted(bins):
            v = np.concatenate(bins[b])
            w.writerow([b * POSITION_BIN, (b + 1) * POSITION_BIN, len(v), float(v.mean()),
                        *(float(np.percentile(v, p)) for p in (50, 90, 99)), float(v.max())])
    with (out / 'throughput_timeline.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['window_start_s', 'window_end_s', 'stream_events', 'events_per_s'])
        for i, count in enumerate(timeline):
            w.writerow([i * TIMELINE_BIN_S, (i + 1) * TIMELINE_BIN_S, int(count), count / TIMELINE_BIN_S])
    return np.concatenate(pooled) if pooled else np.zeros(0, dtype=np.float32)


def summarize(rows, wall_s, pooled):
    successful = [r for r in rows if r['success']]
    valid = [r for r in successful if r['measurement_valid']]
    output = sum(r['completion_tokens'] for r in valid)
    input_tokens = sum(r['prompt_tokens'] for r in valid)
    events = sum(r['stream_events'] for r in valid)
    s = {'requests': len(rows), 'successful_requests': len(successful),
         'failed_requests': len(rows) - len(successful),
         'valid_measurements': len(valid), 'invalid_measurements': len(successful) - len(valid),
         'error_rate': (len(rows) - len(successful)) / len(rows) if rows else None,
         'duration_s': wall_s, 'total_output_tokens': output, 'total_input_tokens': input_tokens,
         'request_throughput_rps': len(successful) / wall_s if wall_s > 0 else None,
         'output_throughput_tps': output / wall_s if wall_s > 0 else None,
         'input_throughput_tps': input_tokens / wall_s if wall_s > 0 else None,
         'total_throughput_tps': (output + input_tokens) / wall_s if wall_s > 0 else None,
         'itl_source': 'client stream-event intervals',
         'itl_token_coverage': events / output if output else 0,
         'itl_coverage': sum(r['stream_events'] == r['completion_tokens'] for r in valid) / len(valid) if valid else 0}
    if valid:
        # Steady decode: after every stream has its first token and before any finishes.
        all_started = max(r['first_token_s'] for r in valid)
        first_done = min(r['last_token_s'] for r in valid)
        s['steady_window_s'] = max(0.0, first_done - all_started)
        s['steady_decode_tps'] = (sum(
            (min(r['last_token_s'], first_done) - max(r['first_token_s'], all_started)) / (
                r['last_token_s'] - r['first_token_s']) * (r['completion_tokens'] - 1)
            for r in valid) / s['steady_window_s']) if s['steady_window_s'] > 0 else None
    for key in ['ttft_ms', 'tpot_ms', 'e2e_ms', 'output_tps', 'decode_tps', 'client_queue_ms',
                'prompt_tokens', 'completion_tokens', 'itl_token_coverage']:
        s.update(distribution(key, [r.get(key) for r in valid]))
    if len(pooled):
        for t in STALL_MS:
            over = pooled[pooled > t]
            s[f'itl_over_{t}ms'] = int(len(over))
            s[f'itl_over_{t}ms_per_request'] = len(over) / len(valid)
        s['itl_over_100ms_stalled_s_per_request'] = float(pooled[pooled > 100].sum() / 1000 / len(valid))
        s.update({'itl_ms_mean': float(pooled.mean()), 'itl_ms_max': float(pooled.max()),
                  **{f'itl_ms_p{p}': float(np.percentile(pooled, p)) for p in (50, 90, 95, 99)},
                  'itl_ms_p99_9': float(np.percentile(pooled, 99.9)), 'itl_samples': int(len(pooled))})
    return s


def finish(out, rows, wall, a, extra, metadata, deployment):
    """Derived tables and summary; shared by measured runs and --reanalyze."""
    pooled = derived_tables(out, rows, wall)
    summary = summarize(rows, wall, pooled)
    summary.update(server_histograms(out, len(a.metrics_url)))
    summary.update(run_id=metadata['run_id'], timestamp_utc=metadata['timestamp_utc'], technology=a.technology,
                   backend=a.backend, model=a.model, workload=metadata['workload'], concurrency=a.concurrency,
                   client_processes=a.processes, sessions=metadata['session_count'], max_model_len=a.max_model_len,
                   requested_output_tokens=a.output_tokens, min_input_tokens=a.min_input_tokens,
                   dataset_sha256=metadata['dataset_sha256'], cache_state=a.cache_state,
                   temperature=a.temperature, ignore_eos=True, label=a.label,
                   extra_body_json=json.dumps(extra, sort_keys=True), image=deployment.get('image', 'unrecorded'),
                   topology=deployment.get('topology', 'unrecorded'), workers=deployment.get('workers', 'unrecorded'),
                   model_revision=deployment.get('model', {}).get('revision', 'unrecorded'),
                   gpu_count=deployment.get('gpu_count', 16),
                   deployment_sha256=hashlib.sha256(json.dumps(deployment, sort_keys=True).encode()).hexdigest())
    write_csv(out / 'summary.csv', [summary])
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


def reanalyze(path):
    """Rebuild derived tables and summary from a finished run's saved files."""
    out = Path(path)
    metadata = json.loads((out / 'metadata.json').read_text())
    a = argparse.Namespace(**{k: metadata[k] for k in vars(parser().parse_args(
        ['--base-url', 'x', '--model', 'x', '--technology', 'dynamo-agg-k8s', '--dataset', 'x',
         '--max-model-len', '1', '--output-tokens', '1']))})
    rows = []
    for p in sorted(out.glob('rows-*.jsonl')):
        rows += [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    rows.sort(key=lambda r: r['session_index'])
    old = json.loads((out / 'summary.json').read_text())
    summary = finish(out, rows, old['duration_s'], a, metadata['resolved_extra_body'], metadata,
                     metadata['deployment'])
    print('Reanalyzed', out, summary['valid_measurements'], 'valid')


def run(a):
    sessions = load_sessions(a.dataset, a.sessions, a.max_model_len, a.output_tokens)
    if any(len(s['turns']) != 1 for s in sessions):
        raise ValueError('long_decode expects single-turn sessions (generate with --turns 1)')
    deployment = json.loads(Path(a.deployment).read_text()) if a.deployment else {}
    a.backend = deployment.get('backend', a.backend or 'sglang')
    extra = json.loads(a.extra_body)
    if deployment:
        if deployment.get('technology', a.technology) != a.technology:
            raise ValueError('--technology must match deployment.json')
        if deployment['model']['model_id'] != a.model or deployment['max_model_len'] != a.max_model_len:
            raise ValueError('--model and --max-model-len must match deployment.json')
        extra = deployment['model'].get('request_body', {}) | extra
    reserved = {'messages', 'model', 'stream', 'stream_options', 'max_tokens', 'n', 'ignore_eos', 'nvext'}
    if extra.keys() & reserved:
        raise ValueError('extra-body may not override structural fields: ' + str(extra.keys() & reserved))
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    out = Path(a.results) / run_id; out.mkdir(parents=True, exist_ok=False)
    metadata = {k: v for k, v in vars(a).items()}
    metadata.update(run_id=run_id, timestamp_utc=datetime.now(timezone.utc).isoformat(),
                    runner='benchmarks.long_decode', ignore_eos=True,
                    dataset_sha256=hashlib.sha256(Path(a.dataset).read_bytes()).hexdigest(),
                    deployment=deployment, python=sys.version, platform=platform.platform(),
                    resolved_extra_body=extra, load_mode='closed-loop', workload=sessions[0]['workload'],
                    session_count=len(sessions), cpu_count=os.cpu_count())
    (out / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    dataset_meta = Path(a.dataset + '.meta.json')
    if dataset_meta.exists():
        (out / 'dataset.meta.json').write_text(dataset_meta.read_text())

    async def prepare(phase):
        async with httpx.AsyncClient(timeout=httpx.Timeout(a.timeout, connect=30)) as client:
            if phase == 'before':
                models = await client.get(a.base_url.rstrip('/') + '/models'); models.raise_for_status()
                if a.model not in [x['id'] for x in models.json().get('data', [])]:
                    raise ValueError('Requested model is absent from /v1/models')
                for i in range(a.warmup):
                    body = {'model': a.model, 'max_tokens': 16, 'temperature': 0, 'stream': True,
                            'messages': [{'role': 'user', 'content': f'Warmup {run_id}-{i}: say hello.'}],
                            'stream_options': {'include_usage': True}, **extra}
                    row, _ = await stream_request(client, a.base_url, body, a.timeout, time.perf_counter())
                    if not row['success']:
                        raise RuntimeError('Warmup failed: ' + row['error'])
            await snapshot_metrics(client, a.metrics_url, out, phase)

    asyncio.run(prepare('before'))
    jobs = [[] for _ in range(a.processes)]
    for i, sample in enumerate(sessions):
        jobs[i % a.processes].append((i, sample))
    run_start_at = time.perf_counter() + 2  # CLOCK_MONOTONIC on Linux: shared by all processes.
    ctx = multiprocessing.get_context('fork')
    procs = [ctx.Process(target=client_process, args=(i, jobs[i], a, extra, out, run_start_at))
             for i in range(a.processes) if jobs[i]]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    wall = time.perf_counter() - run_start_at
    asyncio.run(prepare('after'))
    rows = []
    for path in sorted(out.glob('rows-*.jsonl')):
        rows += [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    missing = len(sessions) - len(rows)
    if missing or any(p.exitcode for p in procs):
        raise RuntimeError(f'{missing} requests missing; client exit codes {[p.exitcode for p in procs]}')
    rows.sort(key=lambda r: r['session_index'])
    for r in rows:
        r.update(run_id=run_id, backend=a.backend, technology=a.technology, workload=sessions[0]['workload'])
    write_csv(out / 'requests.csv', rows)
    summary = finish(out, rows, wall, a, extra, metadata, deployment)
    print(json.dumps({k: summary[k] for k in ['valid_measurements', 'requests', 'duration_s', 'output_throughput_tps',
                                              'steady_decode_tps', 'ttft_ms_p50', 'tpot_ms_p50', 'itl_ms_p50',
                                              'itl_ms_p99', 'server_itl_ms_p50', 'itl_token_coverage']
                      if k in summary}, indent=2))
    print('Results:', out)
    return 0 if summary['failed_requests'] == 0 and summary['invalid_measurements'] == 0 else 1


def parser():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--base-url', required=True)
    p.add_argument('--model', required=True)
    p.add_argument('--technology', required=True, choices=['dynamo-agg-k8s', 'dynamo-disagg-k8s'])
    p.add_argument('--backend', choices=['vllm', 'sglang'])
    p.add_argument('--dataset', required=True); p.add_argument('--deployment')
    p.add_argument('--max-model-len', type=int, required=True)
    p.add_argument('--min-input-tokens', type=int, default=0)
    p.add_argument('--output-tokens', type=int, required=True, help='Forced exact output length')
    p.add_argument('--concurrency', type=int, default=0, help='In-flight requests; 0 means all sessions at once')
    p.add_argument('--sessions', type=int, default=0, help='0 means all JSONL sessions')
    p.add_argument('--processes', type=int, default=8, help='Client processes parsing streams')
    p.add_argument('--warmup', type=int, default=1)
    p.add_argument('--timeout', type=float, default=10800)
    p.add_argument('--temperature', type=float, default=0)
    p.add_argument('--extra-body', default='{}')
    p.add_argument('--cache-state', choices=['cold', 'warm', 'mixed', 'uncontrolled'], default='uncontrolled')
    p.add_argument('--metrics-url', action='append', default=[])
    p.add_argument('--label', default='', help='Free-form run label, e.g. pilot or measured')
    p.add_argument('--results', default='results')
    return p


def main():
    if len(sys.argv) > 2 and sys.argv[1] == '--reanalyze':
        for path in sys.argv[2:]:
            reanalyze(path)
        return
    p = parser(); a = p.parse_args()
    if min(a.output_tokens, a.max_model_len, a.processes) < 1 or a.timeout <= 0:
        p.error('Tokens, context, processes and timeout must be positive')
    if min(a.min_input_tokens, a.sessions, a.concurrency, a.warmup) < 0:
        p.error('Counts cannot be negative')
    if a.min_input_tokens + a.output_tokens > a.max_model_len:
        p.error('Minimum input plus output exceeds context')
    try:
        raise SystemExit(run(a))
    except (ValueError, RuntimeError, httpx.HTTPError) as exc:
        p.exit(2, f'{exc}\n')


if __name__ == '__main__':
    main()
