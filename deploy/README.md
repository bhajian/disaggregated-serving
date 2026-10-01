# Reference deployments

[Home](../README.md) › Deployments

Runnable implementations of the [blueprint](../blueprint/). Each track is one combination of **orchestrator × engine × topology**, delivered as hand-written, commented files for **Docker Compose** and **Kubernetes**. Each track folder has a step-by-step guide covering deploy, verify, see results and clean up.

![Reference topology: two 8 × B300 servers; Node A runs etcd, the frontend and a GPU worker, Node B runs a GPU worker; Ethernet carries control traffic, InfiniBand carries the KV cache](../assets/diagrams/png/b300-reference.png)

## Deployment matrix

| # | Track | Control plane | Engine | Topology | Docker | Kubernetes | Status |
|---|---|---|---|---|---|---|---|
| 00 | [Prerequisites](prerequisites/) | n/a | n/a | n/a | ✓ | ✓ | Hosts, network, RDMA test, model download |
| 01 | [Aggregated](sites/hgx-b300-2x8/01-aggregated/) | Dynamo | vLLM | 1–2 full replicas | [guide](legacy-compose/01-aggregated/vllm/) | [guide](sites/hgx-b300-2x8/01-aggregated/vllm/) | Reference baseline |
| 01 | [Aggregated](sites/hgx-b300-2x8/01-aggregated/) | Dynamo | SGLang | 1–2 full replicas | [guide](legacy-compose/01-aggregated/sglang/) | [guide](sites/hgx-b300-2x8/01-aggregated/sglang/) | Not yet run on hardware |
| 02 | [Disaggregated](sites/hgx-b300-2x8/02-dynamo-disagg-vllm/) | Dynamo | vLLM | prefill + decode, NIXL over IB | [guide](legacy-compose/02-dynamo-disagg-vllm/) | [guide](sites/hgx-b300-2x8/02-dynamo-disagg-vllm/) | Worker setup initialized on reference hosts |
| 03 | [Disaggregated](sites/hgx-b300-2x8/03-dynamo-disagg-sglang/) | Dynamo | SGLang | prefill + decode, NIXL over IB | [guide](legacy-compose/03-dynamo-disagg-sglang/) | [guide](sites/hgx-b300-2x8/03-dynamo-disagg-sglang/) | Experimental |
| 04 | [Disaggregated](sites/hgx-b300-2x8/04-llm-d-disagg/) | llm-d | vLLM / SGLang | prefill + decode, NIXL over IB | n/a | [vLLM](sites/hgx-b300-2x8/04-llm-d-disagg/vllm/) · [SGLang](sites/hgx-b300-2x8/04-llm-d-disagg/sglang/) | Generated manifests, Qwen 480B |
| 05 | [DeepSeek V4 Pro / H200](sites/nebius-h200-2x8/deepseek-v4-pro/) | Dynamo | SGLang | 2 × TP8 aggregated, or prefill TP8 + decode TP8 | n/a | [guide](sites/nebius-h200-2x8/deepseek-v4-pro/) | Nebius deployment; see guide for validation |
| 06 | [Nemotron 3 Nano / H200](sites/nebius-h200-2x8/nemotron-3-nano/) | Dynamo | SGLang | 2 × TP8 aggregated, or prefill TP8 + decode TP8 | n/a | [guide](sites/nebius-h200-2x8/nemotron-3-nano/) | 128K-input and 8K-in/128K-out comparisons (TP8 and TP4 layouts); reuses track 05's PVCs and serving slots |
| · | Dynamo + TensorRT-LLM | Dynamo | TensorRT-LLM | agg and disagg | planned | planned | [Roadmap](../ROADMAP.md) |
| · | KV-cache offloading | Dynamo | vLLM | tiers: DRAM, NVMe with GDS | planned | planned | [Roadmap](../ROADMAP.md) |

## How to use this folder

1. Complete [00 · Prerequisites](prerequisites/) once.
2. Deploy [01 · Aggregated](sites/hgx-b300-2x8/01-aggregated/) with the engine you plan to compare. This is your baseline.
3. Deploy the disaggregated track for the same engine: [02](sites/hgx-b300-2x8/02-dynamo-disagg-vllm/) for vLLM or [03](sites/hgx-b300-2x8/03-dynamo-disagg-sglang/) for SGLang.
4. Measure both with the same dataset using [benchmarks/](../benchmarks/).
5. Optionally, compare the orchestration layer with [04 · llm-d](sites/hgx-b300-2x8/04-llm-d-disagg/).

## Conventions

- **Run commands from the repository root.** Each step names the node it runs on.
- **One track at a time.** Every track uses all 8 GPUs per node and the same host ports. Stop one before starting the next.
- **Docker site settings** live in [cluster.env.example](legacy-compose/cluster.env.example): IPs, interface, InfiniBand devices and paths. Copy it to `deploy/cluster.env` on each node.
- **Kubernetes placement** uses node labels (`llm-serving/node=node-a|node-b`). Site settings live in each track's `01-site-config.yaml`, and pod IPs come from the Downward API.
- **Every folder has a `deployment.json` run record.** The benchmark copies it into each result, so results always state what was deployed.
- **Model:** NVIDIA Nemotron 3 Ultra 550B-A55B NVFP4 at a pinned revision, except track 04. [Switching models](../reference/models.md#switching-a-reference-deployment-to-another-model) is documented.

## Layer mapping

How the tracks map onto the [serving stack](../blueprint/01-serving-stack.md):

| Layer | 01 | 02 | 03 | 04 |
|---|---|---|---|---|
| Control plane | Dynamo frontend + KV router, etcd | same | same | llm-d gateway + endpoint picker + sidecar |
| Engine | vLLM or SGLang | vLLM | SGLang | vLLM or SGLang |
| Data movement | NCCL (TP) | NCCL + NIXL/UCX | NCCL + NIXL/UCX | NCCL + NIXL/UCX |
| Hardware | 1–2 × 8 × B300 | 2 × 8 × B300 + IB | 2 × 8 × B300 + IB | 2 × 8 × GPU + IB |
