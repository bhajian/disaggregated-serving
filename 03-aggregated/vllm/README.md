# 03 · Aggregated serving · vLLM

[Home](../../README.md) › [03 · Aggregated](../README.md) › vLLM

Aggregated Dynamo deployment with **vLLM** workers. This is the reference engine: its Nemotron 3 Ultra flags come from NVIDIA's Dynamo recipe, and the same image and revision completed worker initialization on the reference hosts.

| Platform | Deploy guide | Files |
|---|---|---|
| Docker Compose | [docker/README.md](docker/README.md) | `node-a.yaml`, `node-b.yaml` |
| Kubernetes | [kubernetes/README.md](kubernetes/README.md) | numbered manifests `00-` … `30-` |

| Setting | Value |
|---|---|
| Image | `nvcr.io/nvidia/ai-dynamo/vllm-runtime:1.4.0`, pinned by digest (bundles vLLM 0.26.0) |
| Model | `nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-NVFP4`, revision `252a02f…` |
| Workers | 1 or 2 replicas × 8 GPUs, TP8, 32K context |

Compare it against: [04 · Disaggregated vLLM](../../04-disaggregated-vllm/).
