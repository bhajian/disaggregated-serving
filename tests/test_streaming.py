import asyncio
import csv
import functools
import json
from pathlib import Path

import httpx
import pytest

from benchmarks.run import request, parser, run
from benchmarks.collect import collect


class Stream(httpx.AsyncByteStream):
    def __init__(self, parts):
        self.parts = parts

    async def __aiter__(self):
        for part in self.parts:
            await asyncio.sleep(.002)
            yield part


def stream_body(ids=True, done=True, error=False):
    chunks = [{'choices': [{'delta': {'role': 'assistant', 'content': ''}}]},
              {'choices': [{'delta': {'reasoning_content': 'consider'}, **({'token_ids': [1]} if ids else {})}]},
              {'choices': [{'delta': {'content': 'hello'}, **({'token_ids': [2]} if ids else {})}]},
              {'choices': [{'delta': {}, 'finish_reason': 'stop'}]},
              {'choices': [], 'usage': {'prompt_tokens': 256000, 'completion_tokens': 2}}]
    if error:
        chunks.insert(2, {'error': {'message': 'out of memory'}})
    data = b': heartbeat\r\n\r\n' + ''.join('data: ' + json.dumps(x) + '\r\n\r\n' for x in chunks).encode()
    if done:
        data += b'data: [DONE]\r\n\r\n'
    # Deliberately split JSON in the middle of arbitrary transport packets.
    return [data[i:i + 53] for i in range(0, len(data), 53)]


@pytest.mark.asyncio
@pytest.mark.parametrize('ids', [True, False])
async def test_streaming_reasoning_usage_and_fragmented_sse(ids):
    transport = httpx.MockTransport(lambda _: httpx.Response(200, stream=Stream(stream_body(ids=ids))))
    async with httpx.AsyncClient(transport=transport) as client:
        r = await request(client, 'http://test/v1', {'max_tokens': 512}, 5, 250001, 262144)
    assert r['success'] and r['measurement_valid']
    assert r['completion_tokens'] == 2
    assert r['first_content_ms'] > r['ttft_ms']
    assert r['itl_available'] is ids


@pytest.mark.asyncio
@pytest.mark.parametrize('done,error', [(False, False), (True, True)])
async def test_partial_stream_not_counted_successful(done, error):
    transport = httpx.MockTransport(lambda _: httpx.Response(200, stream=Stream(stream_body(done=done, error=error))))
    async with httpx.AsyncClient(transport=transport) as client:
        r = await request(client, 'http://test/v1', {'max_tokens': 512}, 5, 0, 262144)
    assert not r['success']
    assert not r['measurement_valid']


@pytest.mark.asyncio
async def test_context_verification_and_timeout():
    transport = httpx.MockTransport(lambda _: httpx.Response(200, stream=Stream(stream_body())))
    async with httpx.AsyncClient(transport=transport) as client:
        r = await request(client, 'http://test/v1', {'max_tokens': 512}, 5, 300000, 262144)
        timeout = await request(client, 'http://test/v1', {'max_tokens': 512}, .001, 0, 262144)
    assert r['success'] and not r['measurement_valid']
    assert r['measurement_issue'] == 'input_below_requested_minimum'
    assert not timeout['success']


@pytest.mark.asyncio
@pytest.mark.parametrize('backend', ['vllm', 'sglang'])
async def test_runner_writes_real_schema_and_collects(tmp_path, monkeypatch, backend):
    def respond(req):
        if req.url.path == '/v1/models':
            return httpx.Response(200, json={'data': [{'id': 'test-model'}]})
        body = json.loads(req.content)
        if backend == 'sglang':
            assert 'return_token_ids' not in body
        return httpx.Response(200, stream=Stream(stream_body(ids=backend == 'vllm')))
    factory = functools.partial(httpx.AsyncClient, transport=httpx.MockTransport(respond))
    monkeypatch.setattr(httpx, 'AsyncClient', factory)
    dataset = tmp_path / 'data.jsonl'
    dataset.write_text(json.dumps({'id': 's0', 'workload': 'chatbot', 'turns': [
        {'messages': [{'role': 'user', 'content': 'sample'}], 'input_tokens': 256000}]}))
    a = parser().parse_args(['--base-url', 'http://test/v1', '--model', 'test-model',
        '--technology', 'llmd-k8s', '--dataset', str(dataset), '--max-model-len', '262144',
        '--min-input-tokens', '250001', '--results', str(tmp_path / 'results'), '--backend', backend]
        + (['--token-ids'] if backend == 'vllm' else []))
    assert await run(a) == 0
    summary_path = collect(tmp_path / 'results')
    rows = list(csv.DictReader(summary_path.open()))
    assert len(rows) == 1 and rows[0]['valid_measurements'] == '1'
    assert rows[0]['model'] == 'test-model'
    raw = next((tmp_path / 'results').glob('*/requests.jsonl'))
    assert json.loads(raw.read_text())['chunks'][1]['token_ids'] == ([1] if backend == 'vllm' else None)
    assert rows[0]['backend'] == backend
    assert json.loads(raw.read_text())['backend'] == backend


@pytest.mark.asyncio
async def test_backend_inference_and_mismatches_fail_before_network(tmp_path):
    dataset = tmp_path / 'data.jsonl'
    dataset.write_text(json.dumps({'id': 's0', 'workload': 'chatbot', 'turns': [
        {'messages': [{'role': 'user', 'content': 'sample'}], 'input_tokens': 1}]}))
    dep = tmp_path / 'deployment.json'
    dep.write_text(json.dumps({'backend': 'sglang', 'technology': 'llmd-k8s',
        'model': {'model_id': 'test'}, 'max_model_len': 32768}))
    args = ['--base-url', 'http://unused/v1', '--model', 'test', '--technology', 'llmd-k8s',
            '--dataset', str(dataset), '--deployment', str(dep), '--max-model-len', '32768']
    with pytest.raises(ValueError, match='--backend must match'):
        await run(parser().parse_args(args + ['--backend', 'vllm']))
    with pytest.raises(ValueError, match='--token-ids uses a vLLM extension'):
        await run(parser().parse_args(args + ['--token-ids']))
