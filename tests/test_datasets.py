import json
import random
from pathlib import Path
import pytest

from benchmarks.generate_dataset import padded_context, turns_for, TokenCounter
from benchmarks.run import load_sessions

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('workload', ['chatbot', 'agentic'])
def test_repeatable_long_trace_with_valid_tool_pairs(workload):
    seed = json.loads((ROOT / f'datasets/seeds/{workload}.jsonl').read_text().splitlines()[0])
    def count(messages, tools=None):
        return len(json.dumps(messages)) // 4
    args = (seed, workload, 3000, count)
    context = padded_context(*args, random.Random(42), 'session-1')
    assert context == padded_context(*args, random.Random(42), 'session-1')
    turns = turns_for(seed, workload, context)
    assert len(turns) == 3
    assert count(turns[0]['messages']) >= 3000
    if workload == 'agentic':
        messages = turns[-1]['messages']
        calls = {t['id'] for m in messages for t in m.get('tool_calls', [])}
        assert all(m['tool_call_id'] in calls for m in messages if m['role'] == 'tool')


def test_no_silent_context_truncation(tmp_path):
    file = tmp_path / 'data.jsonl'
    file.write_text(json.dumps({'id': 'x', 'workload': 'chatbot', 'turns': [
        {'messages': [{'role': 'user', 'content': 'hello'}], 'input_tokens': 262000}]}))
    with pytest.raises(ValueError, match='exceeds context'):
        load_sessions(file, 0, 262144, 512)


def test_real_transformers_template_counts_ids_not_batch_encoding_keys(tmp_path):
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace
    from transformers import PreTrainedTokenizerFast
    core = Tokenizer(WordLevel({'[UNK]': 0}, unk_token='[UNK]'))
    core.pre_tokenizer = Whitespace()
    tokenizer = PreTrainedTokenizerFast(tokenizer_object=core, unk_token='[UNK]')
    tokenizer.chat_template = "{% for m in messages %}{{ m['role'] }}: {{ m['content'] }} {% endfor %}assistant:"
    tokenizer.save_pretrained(tmp_path)
    counter = TokenCounter(tokenizer=str(tmp_path))
    assert counter([{'role': 'user', 'content': 'one two three four five six'}]) == 10


def test_deepseek_encoder_requires_trust(tmp_path):
    with pytest.raises(ValueError, match='trust-remote-code'):
        TokenCounter(tokenizer=str(tmp_path), deepseek_v4_encoder=tmp_path / 'encoder.py')


def test_deepseek_encoder_preserves_tool_arguments_and_counts_without_extra_bos(tmp_path):
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace
    from transformers import PreTrainedTokenizerFast
    core = Tokenizer(WordLevel({'[UNK]': 0}, unk_token='[UNK]'))
    core.pre_tokenizer = Whitespace()
    tokenizer = PreTrainedTokenizerFast(tokenizer_object=core, unk_token='[UNK]')
    tokenizer.save_pretrained(tmp_path)
    # No Jinja template: the model's Python encoder supplies its own prompt.
    encoder = tmp_path / 'encoder.py'
    encoder.write_text('''
def encode_messages(messages, thinking_mode, reasoning_effort, drop_thinking):
    assert thinking_mode == 'chat'
    assert messages[0]['role'] == 'system'
    assert messages[0]['tools'][0]['function']['name'] == 'read_file'
    assert messages[2]['tool_calls'][0]['function']['arguments'] == '{"path": "a.py"}'
    messages[1]['content'] = 'mutated'
    return 'BOS user text assistant'
''')
    messages = [{'role': 'user', 'content': 'read a.py'},
                {'role': 'assistant', 'content': None, 'tool_calls': [
                    {'function': {'name': 'read_file', 'arguments': '{"path": "a.py"}'}}]}]
    tools = [{'type': 'function', 'function': {'name': 'read_file'}}]
    counter = TokenCounter(tokenizer=str(tmp_path), trust=True,
                           template_kwargs={'thinking': False}, deepseek_v4_encoder=encoder)
    assert counter(messages, tools) == 4
    assert messages[0]['content'] == 'read a.py'
    assert len(messages) == 2
