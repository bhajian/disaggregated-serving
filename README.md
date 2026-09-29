# Two-node disaggregated inference lab

Run **one TP8 prefill worker on Node A and one TP8 decode worker on Node B**, then compare Dynamo and llm-d using the same workloads. Each worker loads a complete model, sharded over its eight local B300 GPUs.

The original [manual Docker guide](docker-nemotron-dynamo-disaggregated.md) is unchanged.

| Deliverable | Start here |
|---|---|
| Dynamo with Docker Compose | [Compose runbook](docs/compose.md), [files](deployments/compose/) |
| Dynamo on Kubernetes, ordinary Deployments | [Kubernetes runbook](docs/dynamo-kubernetes.md), [all YAML files](deployments/kubernetes/dynamo/) |
| llm-d + vLLM or SGLang P/D on Kubernetes | [llm-d runbook](docs/llmd-kubernetes.md), [files](deployments/kubernetes/llm-d/) |
| vLLM / SGLang switching | [Backend guide](docs/backends.md) |
| Model switching | [Model guide](docs/models.md), [model catalog](configs/models.yaml) |
| Long-context and multi-turn benchmarks | [Benchmark guide](docs/benchmarking.md), [scripts](benchmarks/), [seed datasets](datasets/seeds/) |
| CSV comparison and charts | [Notebook](notebooks/compare.ipynb) |

## Setup

Use Python 3.11+ on the machine running generation/benchmarks. Run all commands from the repository root.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Edit [configs/cluster.yaml](configs/cluster.yaml). The private IPs come from your guide; replace `prefill-node` and `decode-node` with the real **Kubernetes node names**. The checked-in deployments start at 32K. The llm-d example defaults to Qwen 480B FP8; the Dynamo examples default to Nemotron Ultra.

```bash
# Render your own concrete files; this does not contact or modify a cluster.
python scripts/render.py --target compose --model nemotron-ultra --out build/compose
python scripts/render.py --target dynamo --model nemotron-ultra --out build/dynamo
python scripts/render.py --target llmd --model qwen-480b --out build/llmd
```

Add `--backend sglang` to any render command to select SGLang; `--backend vllm` is the default. See the [backend guide](docs/backends.md) for engine-specific images, switching steps and comparison commands.

For the first >250K experiment, render with `--max-model-len 262144 --max-num-seqs 4`, generate approximately **256,000 input tokens**, and reserve 512 output tokens. Check every full turn against the limit; a 262,144-token input cannot also reserve output within a 262,144-token model window.

Run one deployment technology/model at a time. These examples consume all 16 GPUs and reuse host ports. Follow the relevant runbook to stop the previous workers before switching.

## Validation status

Local tests cover metrics, fragmented SSE, failures/timeouts, context-budget checks, manifest generation, and CSV collection. The notebook is checked with empty and simulated results. Kubernetes files are rendered and schema-checked locally. **No deployment, RDMA transfer, model inference or performance measurement has been run on your servers.** No performance results are fabricated.

Nemotron preserves the supplied pinned runtime. DeepSeek and Kimi configurations are experimental adaptations to this TP8/TP8 topology. Kimi automatically selects NVIDIA's model-specific Dynamo preview image and requires additional disk capacity. See [model constraints](docs/models.md) and [source/version notes](docs/sources.md).

```bash
python -m pytest -q
python scripts/validate.py
```

`requirements-lock.txt` records the locally tested Python dependency versions. Schema validation downloads upstream schemas into `build/schema-cache` and does not access your Kubernetes cluster.
