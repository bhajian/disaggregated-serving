# HGX B300 2 × 8 — reference topology (UNVALIDATED)

[Home](../../../README.md) › [Deploy](../../README.md) › [Sites](../README.md) › hgx-b300-2x8

> **UNVALIDATED — scheduled.** These tracks serve Nemotron 3 Ultra 550B-A55B NVFP4 on
> two HGX B300 nodes. The manifests pass the offline structural tests in `tests/`, but
> no run on B300 hardware is recorded in `results/`. The validation plan is
> [experiments/09-b300-reference-validation](../../../experiments/09-b300-reference-validation/).

| Track | Topology | Engine |
| --- | --- | --- |
| [01-aggregated](01-aggregated/) | Two aggregated replicas | vLLM or SGLang |
| [02-dynamo-disagg-vllm](02-dynamo-disagg-vllm/) | Prefill + decode over NIXL | vLLM |
| [03-dynamo-disagg-sglang](03-dynamo-disagg-sglang/) | Prefill + decode over NIXL | SGLang |
| [04-llm-d-disagg](04-llm-d-disagg/) | llm-d prefill/decode with Gateway API Inference Extension | vLLM or SGLang |

The equivalent single-node-debugging Docker Compose files are in
[deploy/legacy-compose](../../legacy-compose/).
