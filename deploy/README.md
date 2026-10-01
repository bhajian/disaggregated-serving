# Deploy

[Home](../README.md) › Deploy

**Executive summary.** Two ways to deploy. The **production path** is operator-managed:
DynamoGraphDeployments ([base/](base/)) composed with a production overlay
([overlays/production/](overlays/production/)) that adds the gateway, TLS and auth,
NetworkPolicies, RDMA via device plugin, the Planner and observability. It is
**UNVALIDATED** on hardware. The **lab path** is the hand-written manifests that produced
every measured result, kept unchanged under each site profile's `lab/` folder.

| Folder | Contents | Status |
| --- | --- | --- |
| [operator/](operator/) | dynamo-platform 1.4.0 Helm values: Kubernetes discovery, Grove + KAI, cert-manager webhook | UNVALIDATED |
| [base/](base/) | One `nvidia.com/v1beta1` DynamoGraphDeployment per model, aggregated and disaggregated variants under one graph name | UNVALIDATED |
| [overlays/](overlays/) | `production/` (gateway, auth, rate limits, NetworkPolicies, Planner, profiling, site patches, NVIDIA operators) and a lab-versus-production diff | UNVALIDATED |
| [observability/](observability/) | PodMonitors, alert rules, Grafana dashboard, canary | UNVALIDATED |
| [sites/nebius-h200-2x8/](sites/nebius-h200-2x8/) | Validated site: DeepSeek V4 Pro and Nemotron 3 Nano lab variants, shared static-PV storage, reports | **Validated** (lab path) |
| [sites/hgx-b300-2x8/](sites/hgx-b300-2x8/) | Reference tracks 01–04 for Nemotron 3 Ultra 550B on B300 | UNVALIDATED reference topology |
| [legacy-compose/](legacy-compose/) | Docker Compose equivalents of the B300 tracks | Single-node debugging only |
| [prerequisites/](prerequisites/) | Host checks, RDMA test, model download | — |

Site values (node names, addresses, kube context, domains, storage classes) are never
committed. Copy [site.env.example](site.env.example) to `deploy/site.env` and render:

```bash
python tools/render_site.py --env deploy/site.env deploy --out build/site
kubectl --context "$KUBE_CONTEXT" apply -k build/site/overlays/production/nemotron-3-nano-h200/aggregated
```

Order for a new cluster: [operator](operator/) → [GPU and Network Operators](overlays/production/operators/) →
[observability](observability/) → [gateway](overlays/production/gateway/) → a model's `namespace/` bundle →
its `aggregated/` or `disaggregated/` graph. [experiments/00-site-migration](../experiments/00-site-migration/)
walks the H200 site through exactly this.
