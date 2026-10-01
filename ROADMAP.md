# Roadmap

[Home](README.md) › Roadmap

What the [blueprint](blueprint/) describes but [deploy/](deploy/) does not yet implement, and how each item will be delivered. Every new track follows the same conventions as the existing ones: hand-written Docker and Kubernetes files, a step-by-step README, a `deployment.json` run record, and offline consistency tests. See [CONTRIBUTING.md](CONTRIBUTING.md).

| Item | Blueprint | Deliverable | Status |
|---|---|---|---|
| **Hardware validation of existing tracks** | [07](blueprint/07-hardware-network-storage.md) | End-to-end RDMA transfer proof and benchmark results for tracks 01–04 on the reference B300 hosts | Next |
| **Dynamo + TensorRT-LLM** | [05](blueprint/05-inference-engines.md) | `deploy/05-dynamo-trtllm/`: aggregated and disaggregated (`dynamo.trtllm`, cache transceiver over NIXL/UCX), Docker and Kubernetes | Planned |
| **KV-cache offloading, phase 0: host readiness** | [08](blueprint/08-kv-cache-and-offloading.md) | NVMe layout, GDS install, `gdscheck` / `gdsio` baselines, GPU Operator GDS option | Planned |
| **KV-cache offloading, phase 1: host DRAM (G2)** | [08](blueprint/08-kv-cache-and-offloading.md) | Aggregated vLLM with KVBM or native offloading. Exit: lower TTFT on returning turns under forced eviction. | Planned |
| **KV-cache offloading, phase 2: local NVMe with GPUDirect Storage (G3)** | [08](blueprint/08-kv-cache-and-offloading.md) | G2 + G3 on aggregated, then disaggregated (`kvbm` + `nixl`). Exit: measured G3 hit rate and TTFT gain at larger working sets. | Planned |
| **KV-cache offloading, phase 3: shared storage (G4)** | [08](blueprint/08-kv-cache-and-offloading.md) | GDS-capable shared file-system tier. Exit: a prefix computed on one node is reused on another. | Planned |
| **SGLang HiCache variants** | [08](blueprint/08-kv-cache-and-offloading.md) | HiCache on tracks 01 and 03, same benchmark | Planned |
| **Hand-annotated llm-d for Nemotron** | [04](blueprint/04-orchestration-layer.md) | Replace the generated track-04 manifests with commented ones, labels and Downward API, and the same model as the Dynamo tracks | Planned |
| **Operator-managed Dynamo** | [10](blueprint/10-production-operations.md) | `DynamoGraphDeployment` variants of tracks 01–02 with Planner autoscaling | Planned |
| **Wide-EP MoE on rack-scale NVLink** | [06](blueprint/06-model-architectures.md), [09](blueprint/09-parallelism-and-sizing.md) | P/D with wide-EP decode for a DeepSeek-class model on GB200/GB300 NVL72 | Planned (needs NVL72 access) |
| **E/P/D multimodal** | [03](blueprint/03-disaggregation-pattern.md) | Separate encode stage for a vision-language model | Exploring |
| **Next-generation hardware** | [07](blueprint/07-hardware-network-storage.md) | Vera Rubin / Rubin CPX guidance as platforms become available | Exploring |

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
