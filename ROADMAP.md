# Roadmap

[Home](README.md) › Roadmap

Items that are designed but not yet validated on hardware. The headline matrix in the
[README](README.md) lists only what has run end to end with recorded results; every
other topology lives here until it does. Target dates are **proposed** and owned by the
maintainers; each row names the experiment that closes it. Experiments are prepared
in [experiments/](experiments/) and have not been run unless `results/` says so.

| Item | Blueprint | Deliverable | Status | Target (proposed) |
|---|---|---|---|---|
| **B300 reference tracks 01–04** | [07](blueprint/07-hardware-network-storage.md) | End-to-end run of the HGX B300 reference topology (`deploy/sites/hgx-b300-2x8`): RDMA transfer proof and benchmark results for aggregated, Dynamo vLLM/SGLang P/D and llm-d | UNVALIDATED — [experiment 09](experiments/09-b300-reference-validation/) | 2026-10-30 |
| **Operator-managed Dynamo on H200** | [10](blueprint/10-production-operations.md) | `DynamoGraphDeployment` aggregated and disaggregated graphs, Planner, KV router, HA frontends ([deploy/base](deploy/base/), [overlays/production](deploy/overlays/production/)) | Manifests written, UNVALIDATED — experiments [01](experiments/01-pd-ratio-sweep/)–[03](experiments/03-planner-demo/) | 2026-10-09 |
| **P:D ratio sweep with goodput at SLO** | [03](blueprint/03-disaggregation-pattern.md), [09](blueprint/09-parallelism-and-sizing.md) | TP2/TP4 prefill with 3–6 decode workers against 4 aggregated replicas, open-loop arrivals | UNVALIDATED — [experiment 01](experiments/01-pd-ratio-sweep/) | 2026-10-05 |
| **DeepSeek V4 Pro DP-attention + EP (+ MTP)** | [06](blueprint/06-model-architectures.md), [09](blueprint/09-parallelism-and-sizing.md) | DP attention with expert parallelism, NEXTN speculative decoding, native FP8 MoE against Marlin | UNVALIDATED — [experiment 05](experiments/05-deepseek-layout/) | 2026-10-12 |
| **Dynamo + TensorRT-LLM** | [05](blueprint/05-inference-engines.md) | Aggregated and disaggregated `dynamo.trtllm` graphs with the cache transceiver over NIXL/UCX | Planned | 2026-11-30 |
| **KV-cache offloading, phase 0: host readiness** | [08](blueprint/08-kv-cache-and-offloading.md) | NVMe layout, GDS install, `gdscheck` / `gdsio` baselines, GPU Operator GDS option | Planned | 2026-11-15 |
| **KV-cache offloading, phase 1: host DRAM (G2)** | [08](blueprint/08-kv-cache-and-offloading.md) | Aggregated vLLM with KVBM or native offloading. Exit: lower TTFT on returning turns under forced eviction. | Planned | 2026-11-30 |
| **KV-cache offloading, phase 2: local NVMe with GPUDirect Storage (G3)** | [08](blueprint/08-kv-cache-and-offloading.md) | G2 + G3 on aggregated, then disaggregated (`kvbm` + `nixl`). Exit: measured G3 hit rate and TTFT gain at larger working sets. | Planned | 2026-12-15 |
| **KV-cache offloading, phase 3: shared storage (G4)** | [08](blueprint/08-kv-cache-and-offloading.md) | GDS-capable shared file-system tier. Exit: a prefix computed on one node is reused on another. | Planned | 2027-01-31 |
| **SGLang HiCache variants** | [08](blueprint/08-kv-cache-and-offloading.md) | HiCache on the aggregated and SGLang P/D graphs, same benchmark | Planned | 2026-12-15 |
| **Hand-annotated llm-d for Nemotron** | [04](blueprint/04-orchestration-layer.md) | Commented llm-d manifests with the same model as the Dynamo graphs | Planned | 2026-11-30 |
| **Wide-EP MoE on rack-scale NVLink** | [06](blueprint/06-model-architectures.md), [09](blueprint/09-parallelism-and-sizing.md) | P/D with wide-EP decode for a DeepSeek-class model on GB200/GB300 NVL72 | Planned (needs NVL72 access) | not scheduled |
| **Vision-language models (E/P/D)** | [03](blueprint/03-disaggregation-pattern.md), [06](blueprint/06-model-architectures.md) | Separate encode stage for a vision-language model; this repository makes no VLM claim until it is measured | Exploring | not scheduled |
| **Next-generation hardware** | [07](blueprint/07-hardware-network-storage.md) | Vera Rubin / Rubin CPX guidance as platforms become available | Exploring | not scheduled |

## KV-cache offloading: planned layout

```text
deploy/
└── 06-kv-offloading/
    ├── README.md
    ├── host-setup/                  phase 0: NVMe + GDS preparation and checks
    ├── aggregated-vllm/             phases 1–2: docker/ and kubernetes/
    ├── disaggregated-vllm/          phases 2–3: docker/ and kubernetes/
    └── sglang-hicache/              SGLang equivalent
```
