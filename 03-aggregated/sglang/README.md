# 03 · Aggregated serving · SGLang

[Home](../../README.md) › [03 · Aggregated](../README.md) › SGLang

Aggregated Dynamo deployment with **SGLang** workers. It uses the same model, context length, concurrency and memory share as the vLLM baseline, so the two engines can be compared directly.

| Platform | Deploy guide | Files |
|---|---|---|
| Docker Compose | [docker/README.md](docker/README.md) | `node-a.yaml`, `node-b.yaml` |
| Kubernetes | [kubernetes/README.md](kubernetes/README.md) | numbered manifests `00-` … `30-` |

| Setting | Value |
|---|---|
| Image | `nvcr.io/nvidia/ai-dynamo/sglang-runtime:1.4.0` (SGLang 0.5.16 base) |
| Model | `nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-NVFP4`, revision `252a02f…` |
| Workers | 1 or 2 replicas × 8 GPUs, TP8, 32K context |
| KV cache dtype | `auto` (vLLM uses `fp8`). Record this difference when comparing engines. |

**Status:** NVIDIA's published Nemotron 3 Ultra SGLang cookbook covers aggregated serving, so this is the lower-risk SGLang path. It has not been run on the reference hosts. Pin the image by digest after your first successful pull ([08](../../08-production-readiness/)).

Compare it against: [05 · Disaggregated SGLang](../../05-disaggregated-sglang/).
