# Troubleshooting

[Home](../README.md) › [Reference](README.md) › Troubleshooting

Most problems fall into one of three layers. Diagnose them in this order, because each layer depends on the one before it.

1. **Control path** over Ethernet: etcd, HTTP and the TCP request plane.
2. **Worker startup:** image, model files and GPU memory.
3. **Data path** over InfiniBand: RDMA KV transfer through NIXL and UCX.

A working etcd connection does **not** prove RDMA works, and a failed etcd connection says nothing about InfiniBand. Keep the checks separate.

## Symptoms and actions

| Symptom | Likely cause | Action |
|---|---|---|
| etcd: `cannot assign requested address` | Listener bound to a specific IP | Keep `--listen-client-urls=http://0.0.0.0:2379`. The advertised URL stays the Node A IP (Docker) or the Service name (Kubernetes). |
| etcd healthy on Node A, unreachable from Node B | Routing or firewall | `ip route get <node-a-ip>` and `curl -v http://<node-a-ip>:2379/health` from Node B. Open 2379 between the private IPs only. |
| Frontend: `Interface not found: 10.x.x.x`, or `TcpListener on fe80::…` / `Invalid argument (os error 22)` | `DYN_TCP_RESPONSE_STREAM_HOST` was set | Remove it. Dynamo 1.4.0 auto-detects IPv4 correctly. No reference file sets it, and a test enforces that. |
| Model missing from `/v1/models` | Workers not registered, or a discovery mismatch | Wait for worker readiness, then read the frontend logs. Check that `DYN_NAMESPACE` and `ETCD_ENDPOINTS` are identical on all components. |
| Worker exits: `Checkpoint revision mismatch` | Different or missing `DEPLOYED_REVISION` | Re-run `tools/download_model.py` on the node. Both nodes must print the same SHA. |
| Worker OOM at startup | Context or concurrency too high for the memory share | Lower `--max-model-len` / `--max-num-seqs`, or keep `--gpu-memory-utilization` at 0.80 until stable |
| GPU busy, or container `already in use` | A previous track or manual container still running | `nvidia-smi`, `docker ps -a`, `kubectl get pods -A -o wide`. Stop it with its own `down` or `delete` command. |
| Request stalls after prefill (disaggregated) | KV transfer cannot connect | Check `UCX_NET_DEVICES` / `IB_DEVICES`, `/dev/infiniband` in the container, `IPC_LOCK` and memlock, side-channel port 5600 (vLLM) or bootstrap port 8998 (SGLang) reachable from Node B, and NIXL/UCX log lines naming the right devices |
| Transfers work but are slow | Staging through host memory, or the wrong interface | Confirm GPUDirect RDMA (`nvidia_peermem` or DMA-BUF). Confirm UCX is using `rc_x`/`rc` on `mlx5_*`, not TCP. Watch the IB port counters. |
| Mamba, cache or backend errors | Mixed engine versions or mismatched roles | Keep the pinned image. Make sure prefill and decode have identical model, TP, block size and KV dtype. Capture the **first** error. |
| Kubernetes pod `Pending` | Missing node label, GPUs taken, or taints | `kubectl describe pod`. Check `kubectl get nodes -L llm-serving/node`. |
| Kubernetes worker advertises the wrong IP | Node InternalIP is not the private IP | `kubectl get nodes -o wide`. Fix the kubelet `--node-ip`. |
| Disk usage climbs | Model copies, images, caches | `docker system df`, `du -sh /data/*/runtime/*`. Logs in the reference files are size-limited. |

## DeepSeek V4 / SGLang stalls after shard loading on network storage

The shard progress bar can reach 100% before GPU copies finish. On the H200
Nebius deployment, native stacks showed concurrent copies blocked in
`cuMemcpyHtoDAsync` / `pthread_rwlock_wrlock`. For checkpoints that fit in host
RAM, enable `--weight-loader-prefetch-checkpoints` and allow time for the cold
disk read; see [SGLang #29268](https://github.com/sgl-project/sglang/issues/29268)
and the [site manifests](../deploy/sites/nebius-h200-2x8/deepseek-v4-pro/). Watch disk-read
and page-cache progress as well as GPU utilization. Do not interpret shard
completion or frontend health as model readiness.

## Useful commands

```bash
# Docker: state and logs (run on the node, from the repository root)
docker compose --env-file deploy/cluster.env -f deploy/<track>/docker/node-a.yaml ps -a
docker compose --env-file deploy/cluster.env -f deploy/<track>/docker/node-a.yaml logs --tail 200 <service>

# Kubernetes
kubectl -n <namespace> get pods -o wide
kubectl -n <namespace> describe pod <pod>
kubectl -n <namespace> logs deployment/<name> --tail 200

# Worker health and metrics
curl -fsS http://<node-ip>:8081/health
curl -s  http://<node-ip>:8081/metrics | grep -Ei 'nixl|transfer|kv'

# InfiniBand
ibv_devinfo -l
cat /sys/class/infiniband/mlx5_4/ports/1/counters/port_xmit_data
```

For the original step-by-step manual deployment, including frontend recovery, see [manual-docker-walkthrough.md](manual-docker-walkthrough.md#10-diagnose-a-failed-check).
