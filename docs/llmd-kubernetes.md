# llm-d + vLLM or SGLang disaggregated serving on Kubernetes

Add `--backend sglang` to the render command to use SGLang. See [backend switching](backends.md) for complete examples, ports and qualification limits; vLLM remains the default.

The pinned version follows the **llm-d v0.10.0** P/D architecture, with router/sidecar **v0.11.0** and vLLM **v0.30.0**. The route is:

```text
Client -> llm-d Router (Envoy + endpoint picker)
       -> Node B routing sidecar :8000
       -> Node A model prefill :8000
       -> NIXL/UCX KV transfer to Node B
       -> Node B model decode :8200 -> streamed response
```

The endpoint picker chooses one worker of each role; the decode sidecar coordinates P/D. This uses the supported **standalone router chart**, so an external Gateway controller is unnecessary. The InferencePool CRD is required. Router fail-open is disabled to avoid a scheduler failure silently becoming an aggregated run.

## Prepare

Use Kubernetes **1.33+** for native sidecar containers (`initContainers.restartPolicy: Always`). Install NVIDIA GPU support, validate RDMA inside pods, edit the node names in `configs/cluster.yaml`, and prepare weights on both nodes as in the [Dynamo runbook](dynamo-kubernetes.md). Helm 3 with OCI support and kubectl are needed on the deployment machine.

The initial example uses **Qwen3-Coder-480B-A35B-Instruct-FP8**, with one TP8 worker per node. See [models](models.md) to select Nemotron, DeepSeek or Kimi. Those combinations still require GPU validation; the llm-d reference's smaller model and different P/D ratio are not performance evidence for these configurations.

## Install cluster dependency and render

```bash
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api-inference-extension/releases/download/v1.5.0/v1-manifests.yaml
python scripts/render.py --target llmd --model qwen-480b --out build/llmd
kubectl apply -f build/llmd/namespace.yaml
kubectl apply --dry-run=server -k build/llmd
# Optional: review all chart-generated resources before installing.
bash scripts/llmd-router.sh render build/llmd
```

The helper pins the chart version and writes `build/llmd/router/rendered.yaml`. The checked-in example also includes a rendered router snapshot. Apply the chart with Helm **or** apply the snapshot, not both. The Kustomization contains only the namespace and worker manifests, keeping chart ownership separate.

```bash
kubectl apply -k build/llmd
bash scripts/llmd-router.sh install build/llmd
kubectl -n llm-d get pods -o wide
kubectl -n llm-d logs -f deployment/prefill -c modelserver
kubectl -n llm-d logs -f deployment/decode -c modelserver
kubectl -n llm-d logs deployment/decode -c routing-proxy --tail=100
kubectl -n llm-d rollout status deployment/prefill --timeout=120m
kubectl -n llm-d rollout status deployment/decode --timeout=120m
```

Both workers use the same local checkpoint, TP, context, block size and cache dtype. With vLLM, prefill uses `kv_producer`; decode uses `kv_consumer` and errors on KV load failure. No remote model download or HF token is needed at worker startup because the weights were downloaded beforehand.

## Test through the router

```bash
kubectl -n llm-d port-forward service/llmd-epp 8000:80
# Another terminal:
curl -fsS http://127.0.0.1:8000/v1/models
curl --fail-with-body --max-time 300 http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8","messages":[{"role":"user","content":"Explain prefill and decode briefly."}],"max_tokens":128,"stream":true,"stream_options":{"include_usage":true}}'
```

Use the router service address from an in-cluster client, or your cluster's configured private service exposure, for actual throughput tests. Do not benchmark Node A's worker directly: it bypasses llm-d and P/D scheduling. Record the chosen API route. For vLLM, `/tokenize` for dataset preparation can target a worker directly, e.g. `http://<B300_NODE_B_IP>:8200`; do not confuse this with the inference target.

With traffic running, inspect `http://<B300_NODE_A_IP>:8000/metrics` and `http://<B300_NODE_B_IP>:8200/metrics`, the sidecar logs, and the router metrics. Confirm transfer counters rise and failures stay zero. Native InfiniBand device selection must appear in the NIXL/UCX logs. Reachable HTTP ports do not prove the data used RDMA.

## Long context and switching

Stop both worker Deployments, wait for their pods to terminate, render the new model/context, then apply and restart. Use the same scale/wait sequence as Dynamo, replacing namespace `dynamo` with `llm-d`.

```bash
python scripts/render.py --target llmd --model qwen-480b \
  --max-model-len 262144 --max-num-seqs 4 --out build/llmd
```

The chart's Envoy route supports long streaming requests, but the pinned chart has other processing timeouts (including a 1000-second ext-proc message timeout). Test the largest prompt end to end. A client timeout cannot increase limits in proxies or sidecars. Check any ingress/load balancer body limits and idle timeouts you add.

To remove the stack:

```bash
helm uninstall llmd -n llm-d
kubectl delete -k build/llmd
```

This removes the dedicated namespace. Shared cluster CRDs and host model/cache data remain.
