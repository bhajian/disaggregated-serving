# Switching between vLLM and SGLang

Every deployment target accepts `--backend vllm|sglang`. vLLM remains the default. The model checkpoint is shared between backends; images, launch flags, parser names and runtime cache directories are selected separately. The chosen backend is written into `deployment.json`.

```bash
# Dynamo Compose: one generated file per host.
python scripts/render.py --target compose --backend sglang --model qwen-480b \
  --max-model-len 262144 --max-num-seqs 4 --out build/compose-sglang

# Dynamo Kubernetes.
python scripts/render.py --target dynamo --backend sglang --model qwen-480b \
  --max-model-len 262144 --max-num-seqs 4 --out build/dynamo-sglang

# llm-d Kubernetes, using its SGLang-aware routing sidecar.
python scripts/render.py --target llmd --backend sglang --model qwen-480b \
  --max-model-len 262144 --max-num-seqs 4 --out build/llmd-sglang
```

Use the generated directory in the [Compose](compose.md), [Dynamo Kubernetes](dynamo-kubernetes.md) or [llm-d](llmd-kubernetes.md) runbook. Checked-in 32K examples are in [compose-sglang](../deployments/compose-sglang/), [dynamo-sglang](../deployments/kubernetes/dynamo-sglang/) and [llm-d-sglang](../deployments/kubernetes/llm-d-sglang/). All three use Qwen 480B. Replace `qwen-480b` with any catalog profile to generate an experimental model configuration.

## What changes

| Setting | vLLM | SGLang |
|---|---|---|
| Dynamo worker | `python3 -m dynamo.vllm` | `python3 -m dynamo.sglang` |
| llm-d worker | `vllm serve` | `python3 -m sglang.launch_server` |
| Dynamo runtime | NVIDIA vLLM runtime 1.4.0 | NVIDIA SGLang runtime 1.4.0, SGLang 0.5.16 base |
| llm-d runtime | vLLM 0.30.0 | SGLang 0.5.20 |
| Worker transfer configuration | `NixlConnector` roles | `--disaggregation-mode` and `--disaggregation-transfer-backend nixl` |
| llm-d sidecar connector | `nixlv2` | `sglang`, bootstrap port 8998 |
| Context argument | `--max-model-len` | `--context-length` |
| Concurrency argument | `--max-num-seqs` | `--max-running-requests` |
| Prefill budget argument | `--max-num-batched-tokens` | `--chunked-prefill-size` |
| Memory fraction argument | `--gpu-memory-utilization` | `--mem-fraction-static` |

The renderer's CLI keeps the existing vLLM-style option names for both engines and maps them to these SGLang flags. These settings have different scheduler semantics; equal numeric values do not guarantee equal memory allocation or scheduling behavior. SGLang has its own page size, cache dtype and parser settings in each model's `sglang` section. Nemotron SGLang uses `auto` KV dtype initially, whereas the supplied vLLM profile uses FP8: record this difference or explicitly qualify matching precision before attributing a performance difference to the engine.

Dynamo workers use port **30000** for SGLang's internal HTTP server, leaving Node A port 8000 for the Dynamo frontend; health remains 8081. llm-d workers use 8000/8200 with the decode proxy on 8000. SGLang's bootstrap port **8998** must be reachable between nodes. NIXL/UCX also requires the private network and RDMA connectivity described in the existing runbooks; these HTTP ports alone are insufficient.

## Stop both old workers before switching

Rendering files does not change a deployment. Both engines consume the same GPUs and host ports. They must run sequentially in this topology.

For Compose, run `docker compose -f OLD_DIRECTORY/node-b.yaml down` on Node B and `docker compose -f OLD_DIRECTORY/node-a.yaml down` on Node A. Start the new directory's etcd, frontend and workers in the documented order. Preserve model files and etcd volumes.

For Kubernetes, use the namespace of the stack you are replacing:

```bash
# Example: change the existing Dynamo deployment to SGLang.
kubectl -n dynamo scale deployment/prefill deployment/decode --replicas=0
kubectl -n dynamo wait --for=delete pod -l app=prefill --timeout=300s
kubectl -n dynamo wait --for=delete pod -l app=decode --timeout=300s
kubectl apply --dry-run=server -k build/dynamo-sglang
kubectl apply -k build/dynamo-sglang
```

For llm-d, substitute namespace `llm-d` and directory `build/llmd-sglang`; apply the router chart as in its runbook if it is not already installed. The generated decode manifest changes both the model server and sidecar together. Switching frameworks also requires stopping the old frontend/etcd or router as described in the runbooks. Switch back by rendering with `--backend vllm` and repeating the same stop/apply/start workflow. Engine caches live under `<runtime_root>/<model>/<stack>/<backend>/<role>`; weights remain read-only and shared.

## Benchmark both engines

Use the same generated workload file and matching context/output budgets. Point inference at the framework frontend/router and retain the matching deployment record:

```bash
python -m benchmarks.run \
  --base-url http://10.104.0.51:8000/v1 \
  --model Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8 \
  --technology dynamo-compose --backend sglang \
  --deployment build/compose-sglang/deployment.json \
  --dataset datasets/generated/qwen-chatbot-256k.jsonl \
  --max-model-len 262144 --min-input-tokens 250001 --output-tokens 512 \
  --concurrency 1 --cache-state uncontrolled
```

`--backend` is optional when supplying `--deployment`: the runner infers it and rejects conflicting labels. Without deployment metadata it defaults to vLLM, so specify it explicitly for SGLang. Each request, summary and metadata record includes `backend`. The comparison notebook uses model × technology × backend and never pools vLLM and SGLang repetitions. Historical CSVs without a backend column are treated as vLLM because the previous version of this repository supported only vLLM.

The runner uses the shared streaming chat API for TTFT, TPOT, TPS and chunk intervals. `--token-ids` is a vLLM-specific extension and is rejected for SGLang. Token-resolved ITL remains unavailable unless the response supplies explicit single-token events that match usage; chunk intervals are not relabeled ITL. The dataset generator's remote `/tokenize` mode uses vLLM's contract, not an assumed SGLang API: use local tokenizer/template files for Qwen, or prepare custom-tokenizer datasets with a compatible vLLM service first. The runner verifies actual SGLang usage counts afterward.

## Qualification status

These are runnable manifest candidates, not measured or GPU-qualified combinations. Begin with Qwen at 32K/concurrency 1, check text and tool output and verify real P/D transfer and RDMA before increasing to >250K. NIXL errors, cancellations and timeouts need particular attention: the pinned llm-d SGLang guide documents cancellation-cleanup limitations.

Nemotron's published SGLang cookbook is an aggregated example; it does not qualify this hybrid-state NIXL P/D adaptation. DeepSeek and Kimi also need model-specific transfer and output checks. Kimi on Dynamo selects the model-specific `sglang-runtime:1.5.0-kimi-k3-dev.1` image with a patched 0.5.17 base; custom images must meet the ordinary 0.5.20 floor. NVIDIA's Kimi SGLang reference uses GB300/NVLink with Mooncake, so the NIXL/InfiniBand adaptation here remains experimental. Do not assume identical parser behavior or KV precision across backends. See [pinned primary references](sources.md).
