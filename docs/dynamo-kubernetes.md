# Dynamo on Kubernetes: two-node deployment

Add `--backend sglang` to the render command to use SGLang. See [backend switching](backends.md) for complete examples, ports and qualification limits; vLLM remains the default.

This version uses ordinary Kubernetes Deployments and a Service. It launches the same Dynamo processes as the manual Docker guide. It **does not require the Dynamo operator/CRDs** and does not implement DynamoGraphDeployment autoscaling, rollout coordination or planner features.

## Cluster preparation

- Two Linux GPU nodes with eight B300s each, compatible drivers, and NVIDIA GPU device plugin/Operator exposing `nvidia.com/gpu`.
- A working CNI and host-to-host RDMA. These lab manifests use host networking to preserve the manual setup's IPs and InfiniBand device names.
- Set real node names in `configs/cluster.yaml`. Ensure each name resolves to the corresponding recorded private IP.
- Download identical weights to the configured `model_path` on both nodes. `hostPath` is deliberate; these are node-pinned workers, not movable model volumes.
- Stop existing manual/Compose/llm-d workers first. They compete for GPUs and host ports.

The default RDMA exposure uses privileged worker containers with `/dev/infiniband`. For an existing Network Operator/device-plugin setup, set `privileged_rdma: false` and `rdma_resource` to the **actual** advertised resource name. Verify access from inside a pod. Merely mounting device files in an unprivileged container does not grant device-cgroup access. The namespace is labeled for privileged lab workloads.

## Render, inspect, deploy

```bash
kubectl get nodes -o wide
python scripts/render.py --target dynamo --model nemotron-ultra --out build/dynamo
kubectl kustomize build/dynamo > build/dynamo-manifests.yaml
kubectl apply --dry-run=server -f build/dynamo-manifests.yaml
kubectl apply -k build/dynamo
kubectl -n dynamo get pods -o wide
kubectl -n dynamo logs -f deployment/prefill
# In a second terminal:
kubectl -n dynamo logs -f deployment/decode
```

On a fresh cluster, create the namespace first if your admission setup requires it before a server dry-run:

```bash
kubectl apply -f build/dynamo/namespace.yaml
```

Workers use `Recreate` because each consumes all eight GPUs on its node. Startup probes allow up to two hours for large checkpoints and compilation. There is no aggressive liveness probe to restart workers during a long prefill.

The folder contains `namespace.yaml`, `etcd.yaml`, `frontend.yaml`, `prefill.yaml`, `decode.yaml`, `service.yaml`, and `kustomization.yaml`. `deployment.json` records the generated configuration for benchmarks. etcd data persists at `/data/disagg/etcd` on Node A; runtime caches persist per model, framework and role.

## Verify

```bash
kubectl -n dynamo rollout status deployment/prefill --timeout=120m
kubectl -n dynamo rollout status deployment/decode --timeout=120m
curl -fsS http://10.104.0.51:8000/v1/models
curl -fsS http://10.104.0.51:8081/health
curl -fsS http://10.104.0.7:8081/health
```

Use the short inference request in the [Compose guide](compose.md), followed by a several-thousand-token streaming request. Observe prefill/decode activity and successful NIXL transfers. For local exploration, `kubectl -n dynamo port-forward service/frontend 8000:8000` works. For throughput measurement, run the load generator on a routable client in the private network; port-forward can become the bottleneck.

## Long context and model switching

```bash
kubectl -n dynamo scale deployment/prefill deployment/decode --replicas=0
# Wait for old worker pods to disappear before applying the new generation.
kubectl -n dynamo wait --for=delete pod -l app=prefill --timeout=10m
kubectl -n dynamo wait --for=delete pod -l app=decode --timeout=10m
python scripts/render.py --target dynamo --model nemotron-ultra \
  --max-model-len 262144 --max-num-seqs 4 --out build/dynamo
kubectl apply -k build/dynamo
```

Stopping both roles first prevents mixed generations and stale peer state during changes. This plain Deployment example does not coordinate a rolling P/D update. Regenerate/restart the frontend too when changing model or cache block size. Increase context/concurrency gradually and watch GPU memory, worker errors and transfer counters.

To stop the whole stack, `kubectl delete -k build/dynamo`. This removes the namespace and its resources; the configured host model/cache/etcd directories remain. Do not put unrelated workloads in this dedicated namespace.
