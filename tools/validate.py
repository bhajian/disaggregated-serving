#!/usr/bin/env python3
"""Validate rendered manifests against upstream schemas (no cluster access)."""
import argparse
import json
from pathlib import Path
import urllib.request

import jsonschema
import yaml


def normalize(obj):
    # Kubernetes OpenAPI v2 expresses IntOrString as type=string + a custom
    # format. JSON Schema needs the equivalent explicit type union.
    if isinstance(obj, dict):
        if obj.get('format') == 'int-or-string' or obj.get('x-kubernetes-int-or-string'):
            obj['type'] = ['string', 'integer']
        for v in obj.values():
            normalize(v)
    elif isinstance(obj, list):
        for v in obj:
            normalize(v)
    return obj


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', action='append',
                   help='Folder to scan; repeatable. Default: every deployment folder in the repository.')
    p.add_argument('--cache-dir', default='build/schema-cache')
    a = p.parse_args()
    cache = Path(a.cache_dir); cache.mkdir(parents=True, exist_ok=True)
    urls = {
        'kubernetes.json': 'https://raw.githubusercontent.com/kubernetes/kubernetes/v1.33.0/api/openapi-spec/swagger.json',
        'compose.json': 'https://raw.githubusercontent.com/compose-spec/compose-spec/main/schema/compose-spec.json',
        'inference.yaml': 'https://github.com/kubernetes-sigs/gateway-api-inference-extension/releases/download/v1.5.0/v1-manifests.yaml'}
    for name, url in urls.items():
        if not (cache / name).exists():
            (cache / name).write_bytes(urllib.request.urlopen(url, timeout=60).read())
    openapi = normalize(json.loads((cache / 'kubernetes.json').read_text()))
    compose = json.loads((cache / 'compose.json').read_text())
    crds = list(yaml.safe_load_all((cache / 'inference.yaml').read_text()))
    crd = next(d for d in crds if d and d['metadata']['name'] == 'inferencepools.inference.networking.k8s.io')
    inference = normalize(next(v['schema']['openAPIV3Schema'] for v in crd['spec']['versions'] if v['name'] == 'v1'))
    count = 0
    roots = a.root or ['03-aggregated', '04-disaggregated-vllm', '05-disaggregated-sglang', '07-llm-d']
    for path in sorted(p for r in roots for p in Path(r).rglob('*.yaml')):
        if path.name in ('kustomization.yaml', 'values.yaml'):
            continue
        for obj in yaml.safe_load_all(path.read_text()):
            if not obj:
                continue
            if 'services' in obj:
                jsonschema.validate(obj, compose)
            else:
                kind, api = obj['kind'], obj['apiVersion']
                if kind == 'InferencePool':
                    schema = inference
                else:
                    group = 'core' if api == 'v1' else api.split('/')[0].split('.')[0]
                    key = f'io.k8s.api.{group}.{api.split("/")[-1]}.{kind}'
                    schema = {'$ref': '#/definitions/' + key, 'definitions': openapi['definitions']}
                jsonschema.Draft4Validator(schema).validate(obj)
            count += 1
    print(f'{count} objects passed upstream structural schema validation. Run server dry-run for cluster admission checks.')


if __name__ == '__main__':
    main()
