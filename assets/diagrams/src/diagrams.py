"""Diagram specs: plain data on a pixel grid (rendered at 2x by tools/render_diagrams.py).

Element types:
  groups  {x, y, w, h, label, style?, badge?}           labelled container
  boxes   {x, y, w, h, label, sub?, style?, size?}      styles: plain soft shade accent solid ghost dark
  arrows  {points: [(x, y), ...], label?, label_at?, style?: accent|muted, dashed?, both?}
  texts   {x, y, text, size?, color?, weight?, ha?}
  points  {x, y, label, style?}
"""

DIAGRAMS = {}

# ----------------------------------------------------------------------------- 1. serving stack
_layers = [
    ('Clients and API edge', 'OpenAI-compatible HTTP · Gateway API + Envoy: TLS, OIDC/JWT, per-tenant rate limits',
     'deploy/overlays/production/gateway'),
    ('Control plane', 'Dynamo frontend: preprocessing, KV-aware router · Planner (SLA autoscaling) · llm-d EPP',
     'deploy/base · overlays/production'),
    ('Inference engines', 'SGLang · vLLM · TensorRT-LLM: continuous batching, paged KV, CUDA graphs, TP/EP/DP',
     'engine flags per profile'),
    ('KV transfer and cache', 'NIXL over UCX: GPUDirect RDMA on InfiniBand, NVLink in-node · KV tiers and offload',
     'UCX / NIXL settings'),
    ('Kubernetes platform', 'Dynamo operator (DynamoGraphDeployment) · Grove + KAI gang scheduling\nWorker discovery through the Kubernetes API (no etcd)',
     'deploy/operator'),
    ('Accelerated infrastructure', 'NVIDIA GPU Operator · Network Operator (RDMA device plugin) · DCGM · HGX H200 / B300',
     'overlays/production/operators'),
]
DIAGRAMS['serving-stack'] = {
    'size': (1400, 760), 'title': 'LLM serving stack',
    'subtitle': 'Each layer depends only on the layer below it. The right column shows where this repository configures it.',
    'boxes': [b for i, (name, detail, where) in enumerate(_layers) for b in (
        {'x': 40, 'y': 110 + i * 100, 'w': 300, 'h': 84, 'label': name, 'style': 'accent' if i in (1, 3) else 'soft', 'size': 14},
        {'x': 356, 'y': 110 + i * 100, 'w': 720, 'h': 84, 'label': detail, 'style': 'plain', 'size': 11.5, 'weight': 'normal'},
        {'x': 1092, 'y': 110 + i * 100, 'w': 268, 'h': 84, 'label': where, 'style': 'ghost', 'size': 11})],
    'texts': [{'x': 1092, 'y': 88, 'text': 'In this repository', 'size': 11, 'color': 'muted', 'weight': 'bold'},
              {'x': 40, 'y': 724, 'text': 'Green: the layers NVIDIA Dynamo provides. Grey: layers it builds on.', 'size': 11, 'color': 'muted'}],
}

# ----------------------------------------------------------------------------- 2. aggregated vs disaggregated
def _timeline(x0, y, kinds):
    out = []
    for i, k in enumerate(kinds):
        out.append({'x': x0 + i * 62, 'y': y, 'w': 56, 'h': 34, 'label': 'prefill' if k == 'P' else 'decode',
                    'style': 'dark' if k == 'P' else 'soft', 'size': 9, 'weight': 'normal'})
    return out


DIAGRAMS['agg-vs-disagg'] = {
    'size': (1400, 780), 'title': 'Aggregated and disaggregated request paths',
    'subtitle': 'Same 16 GPUs either way. Disaggregation moves each request\'s KV cache (and Mamba state for hybrid models) from a prefill worker to a decode worker.',
    'groups': [
        {'x': 40, 'y': 100, 'w': 640, 'h': 640, 'label': 'Aggregated: every worker runs both phases', 'style': 'ghost'},
        {'x': 720, 'y': 100, 'w': 640, 'h': 640, 'label': 'Disaggregated: separate prefill and decode pools', 'style': 'ghost'},
    ],
    'boxes': [
        {'x': 100, 'y': 150, 'w': 150, 'h': 56, 'label': 'Client'},
        {'x': 310, 'y': 150, 'w': 330, 'h': 56, 'label': 'Frontend · KV-aware router'},
        {'x': 100, 'y': 280, 'w': 540, 'h': 160, 'label': 'Aggregated worker', 'sub': 'one batch: new prompts\' prefill chunks run between decode steps', 'style': 'soft'},
        *_timeline(122, 370, 'DDPDDDPD'),
        {'x': 780, 'y': 150, 'w': 150, 'h': 56, 'label': 'Client'},
        {'x': 990, 'y': 150, 'w': 330, 'h': 56, 'label': 'Frontend · KV-aware router'},
        {'x': 780, 'y': 290, 'w': 230, 'h': 140, 'label': 'Prefill worker', 'sub': 'computes the prompt\'s\nKV cache and Mamba state', 'style': 'accent'},
        {'x': 1090, 'y': 290, 'w': 230, 'h': 140, 'label': 'Decode worker', 'sub': 'generates tokens;\nnever runs prefill', 'style': 'soft'},
    ],
    'arrows': [
        {'points': [(250, 178), (310, 178)], 'label': '1 request', 'label_at': (280, 160)},
        {'points': [(475, 206), (475, 280)], 'label': '2 route', 'label_at': (515, 243)},
        {'points': [(140, 440), (140, 490), (70, 490), (70, 178), (100, 178)], 'label': '3 stream tokens', 'label_at': (205, 505), 'dashed': True},
        {'points': [(930, 178), (990, 178)], 'label': '1 request', 'label_at': (960, 160)},
        {'points': [(1080, 206), (930, 290)], 'label': '2 prefill', 'label_at': (965, 240)},
        {'points': [(1010, 360), (1090, 360)], 'style': 'accent', 'label': '3 KV + state', 'label_at': (1050, 340)},
        {'points': [(1205, 430), (1205, 500), (750, 500), (750, 178), (780, 178)], 'label': '4 stream tokens', 'label_at': (980, 515), 'dashed': True},
    ],
    'texts': [
        {'x': 100, 'y': 560, 'text': 'Measured, 8K in / 128K out, 4 × TP4 (results/):', 'size': 11, 'weight': 'bold'},
        {'x': 100, 'y': 586, 'text': 'prefill chunks stalled running streams for up to 13 s;\nworst inter-token gap 40.4 s; highest output tokens/s.', 'size': 11, 'color': 'muted'},
        {'x': 780, 'y': 445, 'text': 'NIXL over UCX: GPUDirect RDMA on InfiniBand\n(cuda_ipc / NVLink when both workers share a node)', 'size': 10.5, 'color': 'accent_ink'},
        {'x': 780, 'y': 560, 'text': 'Measured, 8K in / 128K out, 1 × TP4 prefill + 3 × TP4 decode:', 'size': 11, 'weight': 'bold'},
        {'x': 780, 'y': 586, 'text': 'no prefill stalls; worst gap 1.1 s; TPOT 14.15 vs 14.51 ms;\n1.34× lower tokens/s (three decode workers, not four).', 'size': 11, 'color': 'muted'},
    ],
}
for g in DIAGRAMS['agg-vs-disagg']['groups']:
    g['h'] = 560
DIAGRAMS['agg-vs-disagg']['size'] = (1400, 700)

# ----------------------------------------------------------------------------- 3. production topology
DIAGRAMS['production-topology'] = {
    'size': (1400, 870), 'title': 'Dynamo production topology on Kubernetes',
    'subtitle': 'What deploy/overlays/production creates for one model. Arrows show requests (solid), KV transfer (green) and control (dashed).',
    'groups': [
        {'x': 330, 'y': 100, 'w': 760, 'h': 610, 'label': 'Namespace per model · one DynamoGraphDeployment', 'style': 'ghost'},
        {'x': 360, 'y': 290, 'w': 330, 'h': 230, 'label': 'Prefill pool', 'style': 'ghost'},
        {'x': 730, 'y': 290, 'w': 330, 'h': 230, 'label': 'Decode pool', 'style': 'ghost'},
        {'x': 1120, 'y': 100, 'w': 240, 'h': 610, 'label': 'Cluster services', 'style': 'ghost'},
    ],
    'boxes': [
        {'x': 40, 'y': 150, 'w': 130, 'h': 70, 'label': 'Clients', 'sub': 'OpenAI API'},
        {'x': 40, 'y': 290, 'w': 260, 'h': 110, 'label': 'Gateway API · Envoy', 'sub': 'TLS termination\nOIDC / JWT auth\nper-tenant rate limits', 'style': 'soft'},
        {'x': 360, 'y': 150, 'w': 330, 'h': 100, 'label': 'Frontend × 2', 'sub': 'KV-aware router, replica sync\nprobes require discovered workers', 'style': 'accent'},
        {'x': 730, 'y': 150, 'w': 330, 'h': 100, 'label': 'Planner (SLA mode)', 'sub': 'reads TTFT / ITL from Prometheus\nsets prefill and decode replicas', 'style': 'accent'},
        {'x': 380, 'y': 330, 'w': 290, 'h': 70, 'label': 'Prefill worker · TP4', 'sub': 'RDMA device · IPC_LOCK', 'style': 'plain'},
        {'x': 380, 'y': 420, 'w': 290, 'h': 70, 'label': 'Prefill worker · TP4', 'sub': 'scaled by the Planner', 'style': 'ghost'},
        {'x': 750, 'y': 330, 'w': 290, 'h': 50, 'label': 'Decode worker · TP4', 'style': 'plain', 'size': 11},
        {'x': 750, 'y': 390, 'w': 290, 'h': 50, 'label': 'Decode worker · TP4', 'style': 'plain', 'size': 11},
        {'x': 750, 'y': 450, 'w': 290, 'h': 50, 'label': 'Decode worker · TP4', 'style': 'plain', 'size': 11},
        {'x': 360, 'y': 560, 'w': 700, 'h': 60, 'label': 'model-weights PVC (ReadWriteMany)', 'sub': 'staged once by a Job · SHA256SUMS · revision checked by an init container', 'style': 'soft'},
        {'x': 360, 'y': 636, 'w': 700, 'h': 50, 'label': 'Default-deny NetworkPolicies: only the gateway reaches the frontend; serving pods reach each other', 'style': 'ghost', 'size': 10.5, 'weight': 'normal'},
        {'x': 1140, 'y': 140, 'w': 200, 'h': 90, 'label': 'Dynamo operator', 'sub': 'reconciles the graph\ninto pods and services', 'style': 'soft'},
        {'x': 1140, 'y': 250, 'w': 200, 'h': 90, 'label': 'Grove + KAI', 'sub': 'gang scheduling of\nprefill and decode', 'style': 'soft'},
        {'x': 1140, 'y': 360, 'w': 200, 'h': 90, 'label': 'Kubernetes API', 'sub': 'worker discovery\n(no etcd, no NATS)', 'style': 'soft'},
        {'x': 1140, 'y': 470, 'w': 200, 'h': 110, 'label': 'Observability', 'sub': 'Prometheus · alert rules\nGrafana · canary', 'style': 'soft'},
        {'x': 40, 'y': 760, 'w': 400, 'h': 80, 'label': 'NVIDIA GPU Operator', 'sub': 'driver + GPUDirect RDMA · GFD labels · DCGM', 'style': 'shade'},
        {'x': 480, 'y': 760, 'w': 420, 'h': 80, 'label': 'NVIDIA Network Operator', 'sub': 'RDMA shared device plugin: rdma/rdma_shared_device_a', 'style': 'shade'},
        {'x': 940, 'y': 760, 'w': 420, 'h': 80, 'label': 'cert-manager', 'sub': 'gateway TLS · operator webhook certificates', 'style': 'shade'},
    ],
    'arrows': [
        {'points': [(105, 220), (105, 290)]},
        {'points': [(300, 345), (330, 345), (330, 200), (360, 200)], 'label': 'HTTPS', 'label_at': (318, 180)},
        {'points': [(525, 250), (525, 330)]},
        {'points': [(640, 250), (895, 290)]},
        {'points': [(670, 365), (750, 365)], 'style': 'accent', 'label': 'NIXL', 'label_at': (710, 350)},
        {'points': [(1060, 200), (1140, 185)], 'dashed': True, 'label': 'scale', 'label_at': (1100, 175)},
        {'points': [(1140, 500), (1060, 500)], 'dashed': True, 'style': 'muted'},
    ],
}

# ----------------------------------------------------------------------------- 4. decision flow
_q = lambda x, y, w, text: {'x': x, 'y': y, 'w': w, 'h': 74, 'label': text, 'style': 'shade', 'size': 12}
DIAGRAMS['decision-flow'] = {
    'size': (1400, 1010), 'title': 'Choosing a topology, engine and control plane',
    'subtitle': 'Answer the questions in order. Any "no" on the left means aggregated replicas with KV-aware routing.',
    'boxes': [
        {'x': 40, 'y': 100, 'w': 660, 'h': 60, 'label': 'Workload: ISL and OSL distributions, request rate, p99 TTFT and ITL targets', 'style': 'plain'},
        _q(40, 200, 660, 'Are prefill and decode both a large share of GPU time,\nat the same time, at your peak load?'),
        _q(40, 320, 660, 'Is p99 inter-token latency a hard SLO?'),
        _q(40, 440, 660, 'Can you tune the P:D ratio? (4+ nodes, or several\nworkers per node, e.g. TP2/TP4 on 8-GPU nodes)'),
        _q(40, 560, 660, 'Is there an RDMA fabric (InfiniBand or RoCE)\nor an NVLink domain for KV transfer?'),
        {'x': 40, 'y': 690, 'w': 660, 'h': 64, 'label': 'Aggregated: KV transfer over TCP would cost more than it saves', 'style': 'soft', 'size': 11.5},
        {'x': 820, 'y': 200, 'w': 540, 'h': 194, 'label': 'Aggregated replicas + KV-aware router', 'sub':
         'simplest to run, best TTFT at low load,\nall GPUs prefill and decode.\nTune chunked prefill to bound decode stalls.\nOn 2 × HGX H200 with TP8 workers this is\nusually the right answer (results/).', 'style': 'soft'},
        {'x': 820, 'y': 560, 'w': 540, 'h': 100, 'label': 'Disaggregated, Planner-managed P:D', 'sub': 'prefill and decode pools sized for the SLO;\nconfirm with a goodput sweep (experiments/01)', 'style': 'accent'},
        _q(820, 700, 540, 'MoE or MLA model (DeepSeek-class, Nemotron Ultra)?'),
        {'x': 820, 'y': 814, 'w': 540, 'h': 76, 'label': 'Per-phase parallelism', 'sub': 'prefill: TP2–TP4 (+EP) · decode: wide EP + DP attention, MTP', 'style': 'accent'},
        {'x': 40, 'y': 830, 'w': 660, 'h': 60, 'label': 'Engine: SGLang · vLLM · TensorRT-LLM, by model support and features', 'style': 'plain', 'size': 11.5},
        {'x': 40, 'y': 910, 'w': 1320, 'h': 60, 'label': 'Control plane: Dynamo operator (graphs, Planner, KV router) on Kubernetes, or llm-d (Gateway API Inference Extension)', 'style': 'plain', 'size': 11.5},
    ],
    'arrows': [
        {'points': [(370, 160), (370, 200)]},
        {'points': [(370, 274), (370, 320)], 'label': 'yes', 'label_at': (395, 297)},
        {'points': [(370, 394), (370, 440)], 'label': 'yes', 'label_at': (395, 417)},
        {'points': [(370, 514), (370, 560)], 'label': 'yes', 'label_at': (395, 537)},
        {'points': [(370, 634), (370, 690)], 'label': 'no', 'label_at': (390, 662)},
        {'points': [(700, 237), (820, 237)], 'label': 'no', 'label_at': (760, 222)},
        {'points': [(700, 357), (820, 357)], 'label': 'no', 'label_at': (760, 342)},
        {'points': [(700, 477), (760, 477), (760, 380), (820, 380)], 'label': 'no', 'label_at': (735, 462)},
        {'points': [(700, 597), (820, 597)], 'label': 'yes', 'label_at': (760, 582), 'style': 'accent'},
        {'points': [(1090, 660), (1090, 700)]},
        {'points': [(1090, 774), (1090, 814)], 'label': 'yes', 'label_at': (1115, 794)},
    ],
}

# ----------------------------------------------------------------------------- 5. when disaggregation wins
DIAGRAMS['when-disaggregation-wins'] = {
    'size': (1400, 830), 'title': 'When disaggregation wins',
    'subtitle': 'Design guidance with the three measured H200 studies placed on it. Region boundaries are qualitative; experiment 01 measures them.',
    'boxes': [
        {'x': 160, 'y': 120, 'w': 360, 'h': 640, 'label': 'Low load', 'sub': 'room in every batch: aggregated has\nthe best TTFT and the fewest moving parts', 'style': 'soft'},
        {'x': 530, 'y': 120, 'w': 820, 'h': 200, 'label': 'High load, prefill-dominated', 'sub': 'aggregated prefills on every GPU;\na fixed prefill pool caps prefill throughput', 'style': 'shade'},
        {'x': 530, 'y': 330, 'w': 820, 'h': 220, 'label': 'High load, both phases substantial', 'sub': 'disaggregation can win on goodput at a tight ITL SLO when P:D is tunable\nUNVALIDATED here: experiments/01-pd-ratio-sweep', 'style': 'accent'},
        {'x': 530, 'y': 560, 'w': 820, 'h': 200, 'label': 'High load, decode-dominated', 'sub': 'aggregated wins on tokens/s; disaggregated removes prefill stalls\nfrom the tail ITL. Which matters depends on the SLO.', 'style': 'shade'},
    ],
    'arrows': [
        {'points': [(160, 780), (1350, 780)], 'label': 'offered load (requests in flight, requests/s) →', 'label_at': (755, 800)},
        {'points': [(140, 760), (140, 120)]},
    ],
    'texts': [
        {'x': 40, 'y': 430, 'text': 'prefill share\nof GPU time\n(ISL vs OSL)', 'size': 11, 'color': 'muted'},
        {'x': 940, 'y': 430, 'text': 'A tighter ITL SLO widens this band: prefill stalls\nin aggregated batches become SLO misses.', 'size': 10.5, 'color': 'accent_ink', 'ha': 'center'},
    ],
    'points': [
        {'x': 190, 'y': 300, 'label': 'Nemotron 3 Nano, 128K in / 256 out,\n4 in flight: aggregated 1.62× faster'},
        {'x': 190, 'y': 390, 'label': 'DeepSeek V4 Pro, 256K in, 4 in flight:\naggregated 5.5× faster;\nPD follow-ups lost prefix reuse'},
        {'x': 1000, 'y': 700, 'label': 'Nemotron 3 Nano, 8K in / 128K out, 384–512 in flight:\naggregated 1.34× tokens/s; worst ITL 40.4 s vs 1.1 s', 'style': 'accent'},
    ],
}

# ----------------------------------------------------------------------------- 6. P:D and per-phase parallelism
DIAGRAMS['pd-parallelism'] = {
    'size': (1400, 770), 'title': 'P:D ratio and per-phase parallelism for MoE and MLA models',
    'subtitle': 'Prefill and decode stress different resources, so each pool gets its own parallelism. Design guidance; see notes for what is measured.',
    'groups': [
        {'x': 40, 'y': 100, 'w': 560, 'h': 520, 'label': 'Prefill pool: compute-bound', 'style': 'ghost'},
        {'x': 800, 'y': 100, 'w': 560, 'h': 520, 'label': 'Decode pool: memory-bandwidth-bound', 'style': 'ghost'},
    ],
    'boxes': [
        {'x': 70, 'y': 150, 'w': 500, 'h': 96, 'label': 'Small TP per worker (TP2–TP4)', 'sub': 'more workers prefill in parallel; long prompts\nsplit across fewer GPUs per worker', 'style': 'soft'},
        {'x': 70, 'y': 266, 'w': 500, 'h': 96, 'label': 'Chunked prefill', 'sub': '4K–16K token chunks; larger chunks lower TTFT\nfor 128K+ prompts (experiments/07)', 'style': 'soft'},
        {'x': 70, 'y': 382, 'w': 500, 'h': 96, 'label': 'Expert parallelism for MoE (optional)', 'sub': 'experts spread across the prefill GPUs', 'style': 'soft'},
        {'x': 830, 'y': 150, 'w': 500, 'h': 96, 'label': 'Wide expert parallelism (EP)', 'sub': 'each GPU holds a slice of the experts;\nall-to-all dispatch every decode step', 'style': 'accent'},
        {'x': 830, 'y': 266, 'w': 500, 'h': 96, 'label': 'DP attention for MLA', 'sub': 'each rank keeps whole sequences\' latent KV:\nno KV duplication across TP ranks', 'style': 'accent'},
        {'x': 830, 'y': 382, 'w': 500, 'h': 96, 'label': 'MTP / speculative decoding', 'sub': 'DeepSeek V4: EAGLE (topk 1) with the NextN head;\nSGLang 0.5.16 also allows DSPARK', 'style': 'accent'},
        {'x': 70, 'y': 498, 'w': 500, 'h': 96, 'label': 'Bottleneck: TTFT under load', 'sub': 'queueing for prefill when the pool is too small', 'style': 'ghost', 'weight': 'normal'},
        {'x': 830, 'y': 498, 'w': 500, 'h': 96, 'label': 'Bottleneck: ITL and batch size', 'sub': 'KV capacity and HBM bandwidth per step', 'style': 'ghost', 'weight': 'normal'},
        {'x': 620, 'y': 260, 'w': 160, 'h': 120, 'label': 'P : D', 'sub': 'ratio follows\nISL × rate vs\nOSL × rate\nand the SLO', 'style': 'plain'},
    ],
    'arrows': [
        {'points': [(600, 430), (800, 430)], 'style': 'accent', 'label': 'KV transfer (NIXL)', 'label_at': (700, 412)},
    ],
    'texts': [
        {'x': 40, 'y': 650, 'text': 'The Dynamo Planner adjusts prefill and decode replicas within one GPU budget (max_gpu_budget); it has no per-role cap in 1.4.0.', 'size': 11, 'color': 'muted'},
        {'x': 40, 'y': 680, 'text': 'Measured on the H200 site: TP8 and TP4 layouts only (results/). DP attention + EP and MTP for DeepSeek V4 Pro are experiment 05.', 'size': 11, 'color': 'muted'},
        {'x': 40, 'y': 710, 'text': 'Do not size a 30B-A3B model like Nemotron 3 Nano at TP8: its weights fit on one GPU; TP2–TP4 workers leave room to tune P:D.', 'size': 11, 'color': 'muted'},
    ],
}


# ----------------------------------------------------------------------------- 7/8. site topologies
def _node(x, y, name, gpu, extra_box, hca0=0):
    boxes = [{'x': x + 24 + (i % 4) * 128, 'y': y + 60 + (i // 4) * 70, 'w': 116, 'h': 58, 'label': gpu, 'sub': f'GPU {i}',
              'style': 'soft', 'size': 11} for i in range(8)]
    boxes.append({'x': x + 24, 'y': y + 210, 'w': 500, 'h': 40, 'label': 'NVLink / NVSwitch (all-to-all within the node)', 'style': 'shade', 'size': 10.5, 'weight': 'normal'})
    # HCA names as recorded in UCX_NET_DEVICES / IB_DEVICES; link speed is not recorded.
    boxes += [{'x': x + 24 + i * 63, 'y': y + 270, 'w': 56, 'h': 48, 'label': f'mlx5\n_{hca0 + i}', 'style': 'plain', 'size': 9}
              for i in range(8)]
    boxes.append(extra_box(x, y))
    return boxes


DIAGRAMS['h200-site'] = {
    'size': (1400, 760), 'title': 'Validated site: 2 × HGX H200 on managed Kubernetes',
    'subtitle': 'Every measured result in results/ comes from this site. Workers used hostNetwork in the lab; the production overlay uses the RDMA device plugin instead.',
    'groups': [
        {'x': 40, 'y': 110, 'w': 560, 'h': 420, 'label': 'Node A', 'style': 'ghost', 'badge': 'VALIDATED', 'badge_color': 'accent_ink'},
        {'x': 800, 'y': 110, 'w': 560, 'h': 420, 'label': 'Node B', 'style': 'ghost', 'badge': 'VALIDATED', 'badge_color': 'accent_ink'},
    ],
    'boxes': [
        *_node(40, 110, 'H200 141 GB', 'H200', lambda x, y: {'x': x + 24, 'y': y + 340, 'w': 500, 'h': 56, 'label': 'Network SSD 1500Gi (RWO)', 'sub': 'weights for both models', 'style': 'shade', 'size': 11}),
        *_node(800, 110, 'H200 141 GB', 'H200', lambda x, y: {'x': x + 24, 'y': y + 340, 'w': 500, 'h': 56, 'label': 'Network SSD 1500Gi (RWO)', 'sub': 'weights for both models', 'style': 'shade', 'size': 11}),
        {'x': 620, 'y': 370, 'w': 160, 'h': 70, 'label': 'InfiniBand', 'sub': '8 HCAs per node\nNIXL / UCX', 'style': 'accent'},
        {'x': 40, 'y': 570, 'w': 1320, 'h': 150, 'label': 'Measured layouts (16 GPUs each)', 'sub':
         'DeepSeek V4 Pro, 256K in: 2 × TP8 aggregated · 1 × TP8 prefill + 1 × TP8 decode\n'
         'Nemotron 3 Nano, 128K in / 256 out: 2 × TP8 aggregated · 1 × TP8 prefill + 1 × TP8 decode\n'
         'Nemotron 3 Nano, 8K in / 128K out: 4 × TP4 aggregated (512 in flight) · 1 × TP4 prefill + 3 × TP4 decode (384 in flight)\n\n'
         'Lab control plane: one Dynamo frontend and a single etcd on node A; in-cluster CPU benchmark client.', 'style': 'plain'},
    ],
    'arrows': [
        {'points': [(564, 405), (620, 405)], 'style': 'accent', 'both': True},
        {'points': [(780, 405), (824, 405)], 'style': 'accent', 'both': True},
    ],
}

DIAGRAMS['b300-reference'] = {
    'size': (1400, 780), 'title': 'Reference topology: 2 × HGX B300 (UNVALIDATED)',
    'subtitle': 'Manifests for tracks 01–04 exist and pass offline tests. No run on this hardware is recorded; validation is experiments/09.',
    'groups': [
        {'x': 40, 'y': 110, 'w': 560, 'h': 420, 'label': 'Node A', 'style': 'ghost', 'badge': 'UNVALIDATED'},
        {'x': 800, 'y': 110, 'w': 560, 'h': 420, 'label': 'Node B', 'style': 'ghost', 'badge': 'UNVALIDATED'},
    ],
    'boxes': [
        *_node(40, 110, 'B300', 'B300', lambda x, y: {'x': x + 24, 'y': y + 340, 'w': 500, 'h': 56, 'label': 'Local NVMe', 'sub': 'pinned model revision', 'style': 'shade', 'size': 11}, hca0=4),
        *_node(800, 110, 'B300', 'B300', lambda x, y: {'x': x + 24, 'y': y + 340, 'w': 500, 'h': 56, 'label': 'Local NVMe', 'sub': 'pinned model revision', 'style': 'shade', 'size': 11}, hca0=4),
        {'x': 620, 'y': 370, 'w': 160, 'h': 70, 'label': 'InfiniBand', 'sub': '8 HCAs per node', 'style': 'ghost'},
        {'x': 40, 'y': 570, 'w': 1320, 'h': 170, 'label': 'Planned tracks (Nemotron 3 Ultra 550B-A55B NVFP4)', 'sub':
         '01 aggregated (vLLM, SGLang) · 02 Dynamo P/D on vLLM · 03 Dynamo P/D on SGLang · 04 llm-d P/D\n'
         'Each track: deploy, verify, prove RDMA transfer with IB counters, benchmark, tear down.', 'style': 'ghost'},
    ],
    'arrows': [
        {'points': [(564, 405), (620, 405)], 'style': 'muted', 'dashed': True},
        {'points': [(780, 405), (824, 405)], 'style': 'muted', 'dashed': True},
    ],
}

# ----------------------------------------------------------------------------- 9. KV cache tiers
_tiers = [('G1  GPU HBM', 'active KV pages for running requests', 'in use on every engine', 'accent'),
          ('G2  Host DRAM', 'offloaded prefixes, seconds to reload', 'roadmap (KV offloading phase 1)', 'soft'),
          ('G3  Local NVMe · GPUDirect Storage', 'large working sets per node', 'roadmap (phase 2)', 'soft'),
          ('G4  Shared storage', 'prefixes reused across nodes', 'roadmap (phase 3)', 'soft')]
DIAGRAMS['kv-cache-hierarchy'] = {
    'size': (1400, 640), 'title': 'KV cache tiers',
    'subtitle': 'Each tier down holds more KV and takes longer to bring back into HBM. Only G1 is used by the measured deployments.',
    'boxes': [b for i, (name, role, status, style) in enumerate(_tiers) for b in (
        {'x': 40, 'y': 130 + i * 104, 'w': 520 + i * 90, 'h': 84, 'label': name, 'sub': role, 'style': style, 'size': 13},
        {'x': 960, 'y': 130 + i * 104, 'w': 400, 'h': 84, 'label': status, 'style': 'ghost', 'size': 11, 'weight': 'normal'})],
    'arrows': [{'points': [(920, 140), (920, 540)]}],
    'texts': [{'x': 960, 'y': 104, 'text': 'Status in this repository', 'size': 11, 'color': 'muted', 'weight': 'bold'},
              {'x': 40, 'y': 570, 'text': 'Down the arrow: more capacity per byte of cost, higher latency to reload a prefix. Plan: ROADMAP.md, KV-cache offloading phases 0-3.',
               'size': 11, 'color': 'muted'}],
}

# ----------------------------------------------------------------------------- 10. KV transfer datapath
DIAGRAMS['kv-transfer-datapath'] = {
    'size': (1400, 600), 'title': 'KV transfer datapath between nodes',
    'subtitle': 'GPUDirect RDMA moves KV pages from prefill HBM to decode HBM without a host copy. Staging through host memory works but is slower.',
    'groups': [
        {'x': 40, 'y': 100, 'w': 520, 'h': 400, 'label': 'Prefill node', 'style': 'ghost'},
        {'x': 840, 'y': 100, 'w': 520, 'h': 400, 'label': 'Decode node', 'style': 'ghost'},
    ],
    'boxes': [
        {'x': 70, 'y': 150, 'w': 460, 'h': 60, 'label': 'SGLang / vLLM → NIXL → UCX (rc, cuda_copy, cuda_ipc)', 'style': 'soft', 'size': 11},
        {'x': 70, 'y': 240, 'w': 200, 'h': 80, 'label': 'GPU HBM', 'sub': 'KV pages', 'style': 'accent'},
        {'x': 330, 'y': 240, 'w': 200, 'h': 80, 'label': 'IB NIC (mlx5)', 'sub': 'GPUDirect RDMA'},
        {'x': 70, 'y': 380, 'w': 460, 'h': 70, 'label': 'Host DRAM', 'sub': 'fallback staging', 'style': 'ghost'},
        {'x': 870, 'y': 150, 'w': 460, 'h': 60, 'label': 'UCX → NIXL → SGLang / vLLM', 'style': 'soft', 'size': 11},
        {'x': 1130, 'y': 240, 'w': 200, 'h': 80, 'label': 'GPU HBM', 'sub': 'KV pages', 'style': 'accent'},
        {'x': 870, 'y': 240, 'w': 200, 'h': 80, 'label': 'IB NIC (mlx5)', 'sub': 'GPUDirect RDMA'},
        {'x': 870, 'y': 380, 'w': 460, 'h': 70, 'label': 'Host DRAM', 'sub': 'fallback staging', 'style': 'ghost'},
        {'x': 600, 'y': 250, 'w': 200, 'h': 60, 'label': 'InfiniBand switch', 'style': 'shade'},
    ],
    'arrows': [
        {'points': [(270, 280), (330, 280)], 'style': 'accent'},
        {'points': [(530, 280), (600, 280)], 'style': 'accent'},
        {'points': [(800, 280), (870, 280)], 'style': 'accent'},
        {'points': [(1070, 280), (1130, 280)], 'style': 'accent'},
        {'points': [(170, 320), (170, 380)], 'dashed': True, 'style': 'muted'},
        {'points': [(1230, 380), (1230, 320)], 'dashed': True, 'style': 'muted'},
    ],
    'texts': [
        {'x': 40, 'y': 530, 'text': 'Prerequisites: GPU Operator with driver.rdma.enabled; RDMA device plugin; IPC_LOCK; UCX_NET_DEVICES naming the IB HCAs.', 'size': 11, 'color': 'muted'},
        {'x': 40, 'y': 556, 'text': 'Proof of transfer: InfiniBand port counters rise on both nodes and sglang:kv_transfer_total_mb is non-zero (dashboard panel).', 'size': 11, 'color': 'muted'},
    ],
}
