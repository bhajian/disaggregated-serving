"""Metric definitions shared by the runner and its regression tests."""
import math
import statistics


def percentile(values, p):
    values = sorted(v for v in values if v is not None and math.isfinite(v))
    if not values:
        return None
    pos = (len(values) - 1) * p / 100
    low, high = math.floor(pos), math.ceil(pos)
    return values[low] + (values[high] - values[low]) * (pos - low)


def distribution(prefix, values):
    values = [v for v in values if v is not None and math.isfinite(v)]
    return {prefix + '_' + k: v for k, v in {
        'mean': statistics.mean(values) if values else None,
        'p50': percentile(values, 50), 'p90': percentile(values, 90),
        'p95': percentile(values, 95), 'p99': percentile(values, 99),
        'max': max(values) if values else None}.items()}


def request_metrics(events, duration_s, completion_tokens):
    """Events contain elapsed seconds and explicit delta-token counts, if sent.

    ITL is client-observed, never engine execution time. It is only available
    when ALL output tokens have one-token events and the usage total agrees.
    Batched/missing token IDs yield chunk intervals and no fabricated ITL.
    """
    times = [e['time_s'] for e in events]
    chunk_intervals = [(b - a) * 1000 for a, b in zip(times, times[1:])]
    exact = bool(events) and completion_tokens == len(events) and all(e['token_count'] == 1 for e in events)
    first = times[0] if times else None
    last = times[-1] if times else None
    decode_s = last - first if times else None
    n = completion_tokens
    return {'ttft_ms': first * 1000 if first is not None else None,
            'e2e_ms': duration_s * 1000,
            'tpot_ms': decode_s * 1000 / (n - 1) if decode_s is not None and n and n > 1 else None,
            'output_tps': n / duration_s if n is not None and duration_s > 0 else None,
            'decode_tps': (n - 1) / decode_s if decode_s and n and n > 1 else None,
            'output_chunks': len(events), 'itl_available': exact,
            'itl_ms': chunk_intervals if exact else [],
            'chunk_intervals_ms': chunk_intervals,
            **distribution('itl_ms', chunk_intervals if exact else []),
            **distribution('chunk_interval_ms', chunk_intervals)}


def summarize(rows, wall_s):
    successful = [r for r in rows if r['success']]
    valid = [r for r in successful if r['measurement_valid']]
    output = sum(r['completion_tokens'] for r in valid)
    input_tokens = sum(r['prompt_tokens'] for r in valid)
    summary = {'requests': len(rows), 'successful_requests': len(successful),
               'failed_requests': len(rows) - len(successful),
               'valid_measurements': len(valid), 'invalid_measurements': len(successful) - len(valid),
               'error_rate': (len(rows) - len(successful)) / len(rows) if rows else None,
               'duration_s': wall_s, 'total_output_tokens': output, 'total_input_tokens': input_tokens,
               'request_throughput_rps': len(successful) / wall_s if wall_s > 0 else None,
               'output_throughput_tps': output / wall_s if wall_s > 0 else None,
               'input_throughput_tps': input_tokens / wall_s if wall_s > 0 else None,
               'total_throughput_tps': (output + input_tokens) / wall_s if wall_s > 0 else None,
               'itl_coverage': sum(r['itl_available'] for r in valid) / len(valid) if valid else 0}
    for key in ['ttft_ms', 'first_content_ms', 'tpot_ms', 'e2e_ms', 'output_tps', 'decode_tps', 'client_queue_ms',
                'prompt_tokens', 'completion_tokens']:
        summary.update(distribution(key, [r.get(key) for r in valid]))
    for key in ['itl_ms', 'chunk_intervals_ms']:
        summary.update(distribution(key, [v for r in valid for v in r[key]]))
    return summary
