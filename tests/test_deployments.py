import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def render(tmp_path, target, model='nemotron-ultra', extra=()):
    return subprocess.run([sys.executable, str(ROOT / 'scripts/render.py'), '--target', target,
                           '--model', model, '--out', str(tmp_path), *extra], capture_output=True, text=True)


def test_compose_has_one_control_plane_and_matching_models(tmp_path):
    assert render(tmp_path, 'compose').returncode == 0
    a = yaml.safe_load((tmp_path / 'node-a.yaml').read_text())['services']
    b = yaml.safe_load((tmp_path / 'node-b.yaml').read_text())['services']
    assert set(a) == {'prefill', 'frontend', 'etcd'} and set(b) == {'decode'}
    assert a['prefill']['environment']['ETCD_ENDPOINTS'] == b['decode']['environment']['ETCD_ENDPOINTS']
    assert a['prefill']['environment']['VLLM_HOST_IP'] != b['decode']['environment']['VLLM_HOST_IP']


@pytest.mark.parametrize('target', ['dynamo', 'llmd'])
def test_nodes_gpu_resources_and_connector(tmp_path, target):
    assert render(tmp_path, target, 'qwen-480b', ['--max-model-len', '262144']).returncode == 0
    deps = [yaml.safe_load((tmp_path / f'{r}.yaml').read_text()) for r in ['prefill', 'decode']]
    specs = [d['spec']['template']['spec'] for d in deps]
    assert specs[0]['nodeSelector'] != specs[1]['nodeSelector']
    for d, s in zip(deps, specs):
        assert d['spec']['strategy']['type'] == 'Recreate'
        assert s['containers'][0]['resources']['limits']['nvidia.com/gpu'] == '8'
        args = s['containers'][0]['command']
        kv = json.loads(args[args.index('--kv-transfer-config') + 1])
        assert kv['kv_connector'] == 'NixlConnector'
        assert '--mamba-backend' not in args
    if target == 'llmd':
        assert specs[1]['initContainers'][0]['restartPolicy'] == 'Always'
        values = yaml.safe_load((tmp_path / 'router/values.yaml').read_text())
        assert values['router']['inferencePool']['failureMode'] == 'FailClose'
        assert values['router']['proxy']['failOpen'] is False


def test_context_and_kimi_image_guards(tmp_path):
    assert render(tmp_path, 'dynamo', 'qwen-480b', ['--max-model-len', '1048576']).returncode != 0
    result = render(tmp_path, 'dynamo', 'kimi-k3')
    assert result.returncode == 0
    config = json.loads((tmp_path / 'deployment.json').read_text())
    assert config['image'].endswith('1.5.0-kimi-k3-dev.1')
    prefill = yaml.safe_load((tmp_path / 'prefill.yaml').read_text())
    command = prefill['spec']['template']['spec']['containers'][0]['command']
    assert '0.28.0' in command and '--dyn-tool-call-parser' in command
    assert render(tmp_path, 'llmd', 'kimi-k3').returncode == 0


@pytest.mark.parametrize('target', ['compose', 'dynamo', 'llmd'])
@pytest.mark.parametrize('model', list(yaml.safe_load((ROOT / 'configs/models.yaml').read_text())))
def test_sglang_uses_own_runtime_flags_parsers_and_transport(tmp_path, target, model):
    assert render(tmp_path, target, model, ['--backend', 'sglang']).returncode == 0
    config = json.loads((tmp_path / 'deployment.json').read_text())
    assert config['backend'] == 'sglang'
    assert 'sglang' in config['image'] and 'vllm' not in config['image']
    for role in ['prefill', 'decode']:
        if target == 'compose':
            services = yaml.safe_load((tmp_path / ('node-a.yaml' if role == 'prefill' else 'node-b.yaml')).read_text())['services']
            c = services[role]; command = c['entrypoint']; env = c['environment']
            assert any('/sglang/' in mount for mount in c['volumes'])
        else:
            spec = yaml.safe_load((tmp_path / f'{role}.yaml').read_text())['spec']['template']['spec']
            c = spec['containers'][0]; command = c['command']
            env = {e['name']: e['value'] for e in c['env']}
        assert not any(k.startswith(('VLLM_', 'DYN_VLLM_')) for k in env)
        assert '--kv-transfer-config' not in command and '--max-model-len' not in command
        assert '--reasoning-parser-plugin' not in command and '--enable-auto-tool-choice' not in command
        assert command[command.index('--disaggregation-mode') + 1] == role
        assert command[command.index('--disaggregation-transfer-backend') + 1] == 'nixl'
        assert command[command.index('--disaggregation-bootstrap-port') + 1] == '8998'
        if target == 'llmd':
            assert 'sglang.launch_server' in command
            assert '--dyn-tool-call-parser' not in command
            if role == 'decode':
                proxy = spec['initContainers'][0]
                assert '--kv-connector=sglang' in proxy['args']
                assert {'name': 'SGLANG_BOOTSTRAP_PORT', 'value': '8998'} in proxy['env']
        else:
            assert 'dynamo.sglang' in command and '--kv-events-config' in command
            assert '--tool-call-parser' not in command and '--reasoning-parser' not in command
            assert command[command.index('--port') + 1] == '30000'
    if target == 'compose':
        front = yaml.safe_load((tmp_path / 'node-a.yaml').read_text())['services']['frontend']['entrypoint']
    elif target == 'dynamo':
        front = yaml.safe_load((tmp_path / 'frontend.yaml').read_text())['spec']['template']['spec']['containers'][0]['command']
    else:
        return
    assert front[front.index('--kv-cache-block-size') + 1] == str(config['model']['sglang']['page_size'])


def test_sglang_custom_image_does_not_inherit_kimi_preview_version_floor(tmp_path):
    assert render(tmp_path, 'dynamo', 'kimi-k3', ['--backend', 'sglang', '--image', 'local/sglang:custom']).returncode == 0
    command = yaml.safe_load((tmp_path / 'prefill.yaml').read_text())['spec']['template']['spec']['containers'][0]['command']
    assert '0.5.20' in command and '0.5.17' not in command
