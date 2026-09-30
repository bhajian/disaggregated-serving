# Diagrams

[Home](../../README.md) › Diagrams

Self-contained SVG files used throughout the blueprint and deployment guides. Each one draws a mechanism: where data flows, which components talk, or what changes between two options.

| Diagram | Shows | Used in |
|---|---|---|
| [serving-stack.svg](serving-stack.svg) | The layered serving stack and its OS analogy, with storage connected directly to GPUs | [README](../../README.md), [blueprint 01](../../blueprint/01-serving-stack.md) |
| [agg-vs-disagg.svg](agg-vs-disagg.svg) | Aggregated vs disaggregated: phase interference, and the one edge disaggregation adds | [blueprint 03](../../blueprint/03-disaggregation-pattern.md) |
| [microservices-analogy.svg](microservices-analogy.svg) | Monolith → microservices mapped to aggregated → disaggregated | [blueprint 03](../../blueprint/03-disaggregation-pattern.md) |
| [disagg-request-flow.svg](disagg-request-flow.svg) | Life of a request across router, prefill and decode | [blueprint 03](../../blueprint/03-disaggregation-pattern.md) |
| [orchestrators.svg](orchestrators.svg) | Dynamo vs llm-d: where routing and P/D coordination live | [blueprint 04](../../blueprint/04-orchestration-layer.md) |
| [model-architectures.svg](model-architectures.svg) | Dense, MoE, MLA, hybrid SSM and sliding-window layer stacks and their KV | [blueprint 06](../../blueprint/06-model-architectures.md) |
| [hardware-scaling.svg](hardware-scaling.svg) | 8-GPU servers vs rack-scale NVLink: where KV and EP can go | [blueprint 07](../../blueprint/07-hardware-network-storage.md) |
| [kv-transfer-datapath.svg](kv-transfer-datapath.svg) | GPUDirect RDMA over rail-optimized InfiniBand, CPU off the path | [blueprint 07](../../blueprint/07-hardware-network-storage.md) |
| [kv-cache-hierarchy.svg](kv-cache-hierarchy.svg) | KV tiers G1–G4, and GPUDirect Storage vs the CPU bounce buffer | [blueprint 08](../../blueprint/08-kv-cache-and-offloading.md) |
| [decision-flow.svg](decision-flow.svg) | Topology decision tree, then control plane and engine | [blueprint 11](../../blueprint/11-decision-guide.md) |
| [reference-topology.svg](reference-topology.svg) | The two-node lab: control vs data networks, ports, roles | [deployments](../../deployments/) |

## Editing

All diagrams come from [build_diagrams.py](build_diagrams.py), which holds a shared palette, type scale and arrow style:

```bash
python assets/diagrams/build_diagrams.py
```

| Colour | Meaning |
|---|---|
| Indigo | Serving control plane (Dynamo, llm-d, routers) |
| Blue | Inference engines, decode |
| Orange | Model architectures, prefill |
| Green | Data movement & memory runtime |
| Slate | Hardware and fabrics |
| Cyan | Storage and KV tiers |
| Purple | Platform & operations |
| **Rose** | **KV-cache movement only** |

Every diagram sits on a white card, so it reads in both GitHub light and dark mode. Keep labels short and put explanations in the surrounding text.
