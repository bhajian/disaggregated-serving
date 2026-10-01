"""The offline validator rejects malformed Dynamo CRs and unknown kinds."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'build/schema-cache'
pytestmark = pytest.mark.skipif(not (CACHE / 'gateway-api.yaml').exists(),
                                reason='schema cache not downloaded; run python tools/validate.py once')


@pytest.fixture(scope='module')
def registry():
    from tools.validate import Registry
    return Registry(CACHE)


def dgd(**component):
    return {'apiVersion': 'nvidia.com/v1beta1', 'kind': 'DynamoGraphDeployment',
            'metadata': {'name': 'x', 'namespace': 'ns'},
            'spec': {'backendFramework': 'sglang', 'components': [
                {'name': 'Frontend', 'type': 'frontend', 'replicas': 2, **component}]}}


def test_valid_dynamo_graph_deployment(registry):
    from tools.validate import validate_objects
    count, errors = validate_objects(registry, [dgd()], 'test')
    assert (count, errors) == (1, [])


@pytest.mark.parametrize('bad', [{'type': 'gateway'}, {'replicas': -1}])
def test_invalid_dynamo_graph_deployment(registry, bad):
    from tools.validate import validate_objects
    count, errors = validate_objects(registry, [dgd(**bad)], 'test')
    assert count == 0 and errors


def test_unknown_kind_is_an_error(registry):
    from tools.validate import validate_objects
    _, errors = validate_objects(registry, [{'apiVersion': 'example.com/v1', 'kind': 'Widget', 'metadata': {'name': 'w'}}], 't')
    assert errors and 'no schema' in errors[0]
