# Tests

[Home](../README.md) › Tests

```bash
python -m pytest -q
```

| File | Covers |
|---|---|
| [test_reference_manifests.py](test_reference_manifests.py) | Hand-written deployments: Compose and Kubernetes launch identical engines. Aggregated equals disaggregated minus the transfer flags. Flags and environment match `tools/render.py`. RDMA only where needed. Run records and Kustomizations are consistent. The broken `DYN_TCP_RESPONSE_STREAM_HOST` setting is never used. Every folder has a README. |
| [test_deployments.py](test_deployments.py) | `tools/render.py` output for all models, engines and targets |
| [test_metrics.py](test_metrics.py), [test_streaming.py](test_streaming.py), [test_datasets.py](test_datasets.py) | Benchmark metrics, SSE streaming edge cases, dataset generation |
| [test_long_decode.py](test_long_decode.py) | Long-decode runner: empty-delta token events, forced-length validation, histogram deltas/quantiles, ITL tables |
| [test_notebook.py](test_notebook.py) | The comparison notebook with empty and simulated results |

The tests run offline and never contact a cluster or GPU. They prove consistency, not that inference works on your hardware.
