# Tools (optional helpers)

[Home](../README.md) › Tools

The reference deployments are hand-written and need **none** of these tools. They help with preparation, validation and power-user tasks. Every tool prints what it does, and none of them touches a cluster unless its name says so (`install`).

| Tool | What it does | Touches servers or cluster? |
|---|---|---|
| [download_model.py](download_model.py) | Downloads one pinned checkpoint from `configs/models.yaml`, checks disk space first, writes `DEPLOYED_REVISION` | Writes to the model directory on the host where you run it |
| [preflight.sh](preflight.sh) | Host inventory: IP, GPUs, InfiniBand devices, model files, revision, memlock | Read-only |
| [render.py](render.py) | Generates Compose or Kubernetes files for **any** model, engine and context from `configs/models.yaml` + `configs/cluster.yaml`. Use it to create variants, then read and diff the output against the hand-written reference. | No. Writes files only. |
| [validate.py](validate.py) | Checks every deployment YAML against the upstream Kubernetes, Compose and InferencePool schemas (downloads the schemas once to `build/schema-cache`) | No |
| [sweep.sh](sweep.sh) | Runs `benchmarks.run` over several concurrency levels and repetitions, then collects results | Sends inference requests |
| [llmd-router.sh](llmd-router.sh) | `render` or `install` the pinned llm-d router Helm chart ([deployments/04](../deployments/04-llm-d-disagg/)) | `install` changes the cluster |

Examples:

```bash
python tools/download_model.py --model nemotron-ultra --check-only
bash tools/preflight.sh /data/nemotron-ultra/model eth0
python tools/render.py --target dynamo --backend sglang --model qwen-480b --max-model-len 262144 --out build/dynamo-sglang-qwen
python tools/validate.py
```

`render.py` output uses hard-coded node names and IPs from `configs/cluster.yaml`, unlike the label- and Downward-API-based reference manifests. The repository's tests check that the reference files launch the same engine flags as `render.py` for Nemotron.
