#!/usr/bin/env python3
"""Generate deterministic, token-counted chatbot and recorded agentic sessions."""
import argparse
import copy
import hashlib
import importlib.util
import json
import random
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


class TokenCounter:
    def __init__(self, tokenizer=None, revision=None, url=None, template_kwargs=None, trust=False,
                 deepseek_v4_encoder=None):
        self.url = url
        self.kwargs = template_kwargs or {}
        self.encoder = None
        if deepseek_v4_encoder:
            if url or not tokenizer or not trust:
                raise ValueError('--deepseek-v4-encoder needs --tokenizer and --trust-remote-code')
            unsupported = self.kwargs.keys() - {'thinking', 'reasoning_effort', 'drop_thinking'}
            if unsupported:
                raise ValueError(f'Unsupported DeepSeek V4 template arguments: {sorted(unsupported)}')
            spec = importlib.util.spec_from_file_location('encoding_dsv4', deepseek_v4_encoder)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.encoder = module.encode_messages
        if not url:
            from transformers import AutoTokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(tokenizer, revision=revision, trust_remote_code=trust)

    def __call__(self, messages, tools=None):
        if self.url:
            body = {'messages': messages, 'add_generation_prompt': True,
                    'chat_template_kwargs': self.kwargs}
            if tools:
                body['tools'] = tools
            r = httpx.post(self.url.rstrip('/') + '/tokenize', json=body, timeout=180)
            r.raise_for_status()
            result = r.json()
            return result['count'] if 'count' in result else len(result['tokens'])
        kwargs = {'tools': tools} if tools else {}
        messages = copy.deepcopy(messages)
        if self.encoder:
            if tools:
                if not messages or messages[0]['role'] != 'system':
                    messages.insert(0, {'role': 'system', 'content': ''})
                messages[0]['tools'] = copy.deepcopy(tools)
            prompt = self.encoder(
                messages, thinking_mode='thinking' if self.kwargs.get('thinking', True) else 'chat',
                reasoning_effort=self.kwargs.get('reasoning_effort'),
                drop_thinking=self.kwargs.get('drop_thinking', True))
            # The official encoder already includes BOS and the assistant prefix.
            return len(self.tokenizer.encode(prompt, add_special_tokens=False))
        for message in messages:
            for call in message.get('tool_calls', []):
                arguments = call.get('function', {}).get('arguments')
                if isinstance(arguments, str):
                    call['function']['arguments'] = json.loads(arguments)
        tokens = self.tokenizer.apply_chat_template(messages, tokenize=True, return_dict=False, add_generation_prompt=True,
                                                **kwargs, **self.kwargs)
        return len(tokens)


TOOLS = [{'type': 'function', 'function': {'name': 'read_file', 'description': 'Read a repository file.',
         'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}}, 'required': ['path']}}},
         {'type': 'function', 'function': {'name': 'run_tests', 'description': 'Run repository tests.',
         'parameters': {'type': 'object', 'properties': {}}}}]


def turns_for(seed, workload, context):
    messages = [{'role': 'system', 'content': seed['system'] + '\nReference records:\n' + context}]
    result = []
    if workload == 'chatbot':
        for i, q in enumerate(seed['questions']):
            messages.append({'role': 'user', 'content': q})
            result.append({'messages': copy.deepcopy(messages)})
            if i < len(seed['answers']):
                messages.append({'role': 'assistant', 'content': seed['answers'][i]})
    else:
        messages.append({'role': 'user', 'content': seed['task']})
        result.append({'messages': copy.deepcopy(messages), 'tools': TOOLS})
        for i, (name, arguments, content) in enumerate([
            (seed['tool_name'], seed['tool_arguments'], seed['tool_result']),
            ('run_tests', {}, seed['test_result'])]):
            messages += [{'role': 'assistant', 'content': None, 'reasoning_content': 'Inspect the available evidence.',
                          'tool_calls': [{'id': f'call_{i}', 'type': 'function', 'function': {
                              'name': name, 'arguments': json.dumps(arguments)}}]},
                         {'role': 'tool', 'tool_call_id': f'call_{i}', 'content': content}]
            if i == 1:
                messages.append({'role': 'user', 'content': seed['followup']})
            result.append({'messages': copy.deepcopy(messages), 'tools': TOOLS})
    return result


def padded_context(seed, workload, target, counter, rng, prefix, corpus=None):
    # Unrelated records have unique IDs. No repeated single-token filler, which
    # would create an unrealistically compressible/cached workload.
    chunks = []
    words = ['queue', 'cache', 'worker', 'tenant', 'version', 'latency', 'request', 'region']
    source = corpus or seed['context']
    pieces = [source[i:i + 1200] for i in range(0, len(source), 1200)]
    total_chars, i = 0, 0
    while total_chars < max(8192, target * 8):
        source_piece = pieces[i % len(pieces)]
        chunks.append(f'\nRecord {i}-{rng.getrandbits(48):012x}: {source_piece} '
                      f'{rng.choice(words)}={rng.randrange(100000)}; status=observed.')
        total_chars += len(chunks[-1]); i += 1
    text = prefix + seed['context'] + ''.join(chunks)
    def count(chars):
        turn = turns_for(seed, workload, text[:chars])[0]
        return counter(turn['messages'], turn.get('tools'))
    if count(len(text)) < target:
        raise ValueError('Corpus too short for requested token target')
    lo, hi = len(prefix) + len(seed['context']), len(text)
    if count(lo) > target:
        raise ValueError('Target shorter than the base prompt')
    # Character-prefix token counts are nearly monotonic. Recount the chosen
    # result and record the actual value; never claim the target is exact.
    best = hi
    while lo <= hi:
        mid = (lo + hi) // 2
        n = count(mid)
        if n >= target:
            best, hi = mid, mid - 1
        else:
            lo = mid + 1
    return text[:best]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workload', choices=['chatbot', 'agentic'], required=True)
    p.add_argument('--input-tokens', type=int, default=256000)
    p.add_argument('--max-model-len', type=int, default=262144)
    p.add_argument('--output-tokens', type=int, default=512)
    p.add_argument('--sessions', type=int, default=8)
    p.add_argument('--turns', type=int, default=0, help='Keep only the first N recorded turns; 0 keeps all')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--tokenizer'); p.add_argument('--revision')
    p.add_argument('--tokenizer-url', help='vLLM worker base URL exposing /tokenize; useful for DeepSeek V4')
    p.add_argument('--trust-remote-code', action='store_true')
    p.add_argument('--deepseek-v4-encoder', help='Checkpoint encoding/encoding_dsv4.py; requires --trust-remote-code')
    p.add_argument('--template-kwargs', default='{}')
    p.add_argument('--corpus', help='Optional local UTF-8 corpus, replacing synthetic record prose')
    p.add_argument('--out', required=True)
    a = p.parse_args()
    if not (a.tokenizer or a.tokenizer_url):
        p.error('Pass --tokenizer (local directory or HF ID), or --tokenizer-url.')
    if min(a.sessions, a.input_tokens, a.output_tokens, a.max_model_len) < 1 or a.turns < 0:
        p.error('Counts must be positive')
    count = TokenCounter(a.tokenizer, a.revision, a.tokenizer_url, json.loads(a.template_kwargs),
                         a.trust_remote_code, a.deepseek_v4_encoder)
    seeds = [json.loads(x) for x in (ROOT / f'datasets/seeds/{a.workload}.jsonl').read_text().splitlines()]
    rng = random.Random(a.seed)
    corpus = Path(a.corpus).read_text() if a.corpus else None
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        p.error('Output already exists; choose a new dataset path.')
    with out.open('w') as f:
        for i in range(a.sessions):
            seed = seeds[i % len(seeds)]
            context = padded_context(seed, a.workload, a.input_tokens, count, rng,
                                     f'Session {a.seed}-{i}-{rng.getrandbits(64):016x}\n', corpus)
            turns = turns_for(seed, a.workload, context)
            if a.turns:
                turns = turns[:a.turns]
            for turn in turns:
                turn['input_tokens'] = count(turn['messages'], turn.get('tools'))
                if turn['input_tokens'] + a.output_tokens > a.max_model_len:
                    raise ValueError('A complete turn plus reserved output exceeds --max-model-len.')
            row = {'id': f'{a.workload}-{a.seed}-{i}', 'workload': a.workload,
                   'kind': 'recorded-trace-replay', 'target_input_tokens': a.input_tokens,
                   'max_output_tokens': a.output_tokens, 'turns': turns}
            f.write(json.dumps(row) + '\n')
            print(row['id'], [t['input_tokens'] for t in turns])
    manifest = vars(a) | {'sha256': hashlib.sha256(out.read_bytes()).hexdigest(),
                          'token_count_source': ('server' if a.tokenizer_url else
                              'deepseek-v4-encoder' if a.deepseek_v4_encoder else 'local-chat-template')}
    if a.deepseek_v4_encoder:
        manifest['encoder_sha256'] = hashlib.sha256(Path(a.deepseek_v4_encoder).read_bytes()).hexdigest()
    out.with_suffix(out.suffix + '.meta.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
