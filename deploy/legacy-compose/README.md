# Legacy Docker Compose (single-node debugging only)

[Home](../../README.md) › [Deploy](../README.md) › Legacy Compose

> **Not a production path.** These Compose files launch the same engines as the
> B300 reference tracks directly on hosts, without Kubernetes, the Dynamo operator,
> health management or network isolation. Use them to debug an engine or transfer
> setup on one or two machines. Production deployments use the
> [Dynamo operator path](../base/).

Each track folder holds `node-a.yaml` / `node-b.yaml` and a `deployment.json` run
record. Site values come from [`cluster.env.example`](cluster.env.example):

```bash
cp deploy/legacy-compose/cluster.env.example deploy/legacy-compose/cluster.env   # edit on both nodes
docker compose --env-file deploy/legacy-compose/cluster.env \
  -f deploy/legacy-compose/02-dynamo-disagg-vllm/node-a.yaml up -d
```
