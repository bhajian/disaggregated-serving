# Dynamo with Docker Compose on two hosts

Add `--backend sglang` to the render command to use SGLang. See [backend switching](backends.md) for complete examples, ports and qualification limits; vLLM remains the default.

Compose manages containers **locally**. Run the Node A file on Node A and the Node B file on Node B; this is not a cross-host Compose scheduler.

Prerequisites are the same as the [manual guide](../docker-nemotron-dynamo-disaggregated.md): Docker Engine on Linux, Compose **2.30+** (`gpus: all`), NVIDIA Container Toolkit, compatible GPU driver, InfiniBand drivers and successful RDMA checks. Use the trusted private network for control and dynamically allocated Dynamo/UCX ports.

## Prepare

1. Stop the manual guide's containers if they are running, using their names from `docker ps`. Avoid running both stacks on the same ports/GPUs. Keep model data.
2. Copy this repository to both nodes. Edit `configs/cluster.yaml` consistently.
3. Reuse `/data/nemotron-ultra/model` for the original pinned Nemotron checkpoint, or download another profile with the [model workflow](models.md). Both nodes need the same complete revision.
4. Generate the same deployment on both nodes:

```bash
python scripts/render.py --target compose --model nemotron-ultra --out build/compose
bash scripts/preflight.sh /data/nemotron-ultra/model
```

The files mount weights read-only, keep frontend and worker caches separate, expose RDMA devices, set unlimited memlock, and retain the manual guide's TCP/ZMQ transport. No NATS or Ray cluster is required.

## Node A: control plane and prefill

```bash
docker compose -f build/compose/node-a.yaml config -q
docker compose -f build/compose/node-a.yaml pull
docker compose -f build/compose/node-a.yaml up -d etcd
curl -fsS http://10.104.0.51:2379/health
# Continue after etcd reports healthy.
docker compose -f build/compose/node-a.yaml up -d frontend prefill
docker compose -f build/compose/node-a.yaml logs -f prefill frontend
```

## Node B: decode

```bash
curl -fsS http://10.104.0.51:2379/health
docker compose -f build/compose/node-b.yaml config -q
docker compose -f build/compose/node-b.yaml pull
docker compose -f build/compose/node-b.yaml up -d
docker compose -f build/compose/node-b.yaml logs -f decode
```

Workers intentionally have no restart loop, making initialization failures visible. Compose `up -d` is not a readiness check.

## Verify and benchmark

```bash
curl -fsS http://10.104.0.51:8000/v1/models
curl -fsS http://10.104.0.51:8081/health
curl -fsS http://10.104.0.7:8081/health
curl --fail-with-body --max-time 300 http://10.104.0.51:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-NVFP4","messages":[{"role":"user","content":"Explain prefill and decode briefly."}],"max_tokens":128,"chat_template_kwargs":{"enable_thinking":false,"force_nonempty_content":true}}'
```

Inspect both worker logs and NIXL metrics under traffic. A 200 response alone does not demonstrate RDMA or prove that the decode worker reused transferred KV. The [benchmark guide](benchmarking.md) uses `--technology dynamo-compose --base-url http://10.104.0.51:8000/v1`.

## Switch or stop

Stop **both** worker stacks before changing model, context, image or cache layout. A partial restart can pair incompatible workers.

```bash
# Node B
docker compose -f build/compose/node-b.yaml down
# Node A
docker compose -f build/compose/node-a.yaml down
```

Regenerate with the new profile and restart in the order above. `down` preserves the named etcd volume and host model/cache directories. Do not use `down -v` for a routine switch. If moving from Compose to Kubernetes, the etcd state is separate, but stop the Compose etcd first because both use port 2379.
