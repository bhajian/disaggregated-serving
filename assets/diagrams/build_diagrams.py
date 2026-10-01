#!/usr/bin/env python3
"""Source for every SVG diagram in assets/diagrams/.

The diagrams are plain, self-contained SVG files that render on GitHub and in
any browser. This script exists so they share one visual system (palette,
type scale, arrow styles) and stay easy to edit. Run it after changing a
diagram:

    python assets/diagrams/build_diagrams.py

Conventions
-----------
* One colour per stack layer (see LAYER below), used consistently everywhere.
* ROSE is reserved for KV-cache movement (the data that disaggregation moves).
* Every diagram sits on a white card, so it reads in GitHub light and dark mode.
"""
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent

FONT = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace"

INK = '#0F172A'        # primary text
MUTED = '#475569'      # secondary text
FAINT = '#94A3B8'      # hairlines, tertiary text
LINE = '#E2E8F0'       # card border, dividers
ROSE = '#E11D48'       # KV-cache movement (the one semantic accent)
ROSE_BG = '#FFF1F2'

# fill, stroke, header-text for each layer of the serving stack
LAYER = {
    'access':   ('#F8FAFC', '#CBD5E1', '#334155'),
    'orch':     ('#EEF2FF', '#818CF8', '#4338CA'),
    'engine':   ('#EFF6FF', '#60A5FA', '#1D4ED8'),
    'model':    ('#FFF7ED', '#FB923C', '#C2410C'),
    'runtime':  ('#F0FDF4', '#4ADE80', '#15803D'),
    'hw':       ('#F1F5F9', '#64748B', '#1E293B'),
    'storage':  ('#ECFEFF', '#22D3EE', '#0E7490'),
    'platform': ('#FAF5FF', '#C084FC', '#7E22CE'),
    'prefill':  ('#FFF7ED', '#F97316', '#C2410C'),
    'decode':   ('#EFF6FF', '#3B82F6', '#1D4ED8'),
    'neutral':  ('#FFFFFF', '#CBD5E1', '#334155'),
}

STYLE = f"""
text {{ font-family: {FONT}; fill: {INK}; }}
.title {{ font-size: 22px; font-weight: 700; letter-spacing: -0.01em; }}
.subtitle {{ font-size: 13.5px; fill: {MUTED}; }}
.h {{ font-size: 11.5px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }}
.lbl {{ font-size: 13px; font-weight: 600; }}
.lbl-lg {{ font-size: 15px; font-weight: 700; }}
.sub {{ font-size: 11.5px; fill: {MUTED}; }}
.small {{ font-size: 11px; fill: {MUTED}; }}
.tiny {{ font-size: 10px; fill: {MUTED}; }}
.note {{ font-size: 11.5px; fill: {MUTED}; font-style: italic; }}
.mono {{ font-family: {MONO}; font-size: 11px; fill: {MUTED}; }}
.edge {{ font-size: 11.5px; font-weight: 600; fill: {MUTED}; }}
.edge-kv {{ font-size: 12px; font-weight: 700; fill: {ROSE}; }}
.num {{ font-size: 11px; font-weight: 700; fill: #FFFFFF; }}
"""


class SVG:
    def __init__(self, w, h, title, subtitle=None, label=None):
        self.w, self.h = w, h
        self.body = []
        self.markers = {}
        self.title, self.subtitle = title, subtitle
        self.label = label or title

    # ---- primitives -------------------------------------------------------
    def add(self, s):
        self.body.append(s)

    def rect(self, x, y, w, h, fill='#fff', stroke=LINE, rx=10, sw=1.2, dash=None, opacity=None):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        o = f' opacity="{opacity}"' if opacity else ''
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="{sw}"{d}{o}/>')

    def text(self, x, y, s, cls='lbl', anchor='start', fill=None, weight=None, size=None, rotate=None):
        # inline style beats the class rules in <style>; presentation attributes would not
        st = []
        if fill:
            st.append(f'fill:{fill}')
        if weight:
            st.append(f'font-weight:{weight}')
        if size:
            st.append(f'font-size:{size}px')
        extra = f' style="{";".join(st)}"' if st else ''
        if rotate is not None:
            extra += f' transform="rotate({rotate} {x} {y})"'
        self.add(f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}"{extra}>{escape(s)}</text>')

    def lines(self, x, y, rows, cls='sub', anchor='start', lh=15, fill=None):
        for i, r in enumerate(rows):
            self.text(x, y + i * lh, r, cls, anchor, fill)

    def line(self, x1, y1, x2, y2, stroke=FAINT, sw=1.2, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        self.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def _marker(self, color):
        mid = 'a' + color.strip('#')
        if mid not in self.markers:
            self.markers[mid] = (f'<marker id="{mid}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" '
                                 f'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" '
                                 f'fill="{color}"/></marker>')
        return mid

    def arrow(self, pts, color=MUTED, sw=1.6, dash=None, both=False):
        mid = self._marker(color)
        d = f' stroke-dasharray="{dash}"' if dash else ''
        start = f' marker-start="url(#{mid})"' if both else ''
        p = ' '.join(f'{x},{y}' for x, y in pts)
        self.add(f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="{sw}" '
                 f'stroke-linejoin="round" stroke-linecap="round"{d}{start} marker-end="url(#{mid})"/>')

    def circle(self, cx, cy, r, fill, stroke='none', sw=1):
        self.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def step(self, cx, cy, n, color=INK):
        self.circle(cx, cy, 10, color)
        self.text(cx, cy + 4, str(n), 'num', 'middle')

    # ---- composites -------------------------------------------------------
    def box(self, x, y, w, h, title, sub=None, theme='neutral', rx=10, sw=1.3, align='middle',
            title_cls='lbl', dash=None, sub_lh=14):
        fill, stroke, head = LAYER[theme]
        self.rect(x, y, w, h, fill, stroke, rx, sw, dash)
        subs = sub if isinstance(sub, (list, tuple)) else ([sub] if sub else [])
        block = 16 + len(subs) * sub_lh
        ty = y + (h - block) / 2 + 13
        tx = x + w / 2 if align == 'middle' else x + 12
        self.text(tx, ty, title, title_cls, align, fill=head if theme != 'neutral' else INK)
        for i, s in enumerate(subs):
            self.text(tx, ty + 16 + i * sub_lh, s, 'sub', align)

    def panel(self, x, y, w, h, heading, theme, sub=None):
        fill, stroke, head = LAYER[theme]
        self.rect(x, y, w, h, fill, stroke, 12, 1.3)
        self.text(x + 14, y + 22, heading, 'h', fill=head)
        if sub:
            self.text(x + w - 14, y + 22, sub, 'small', 'end')

    def chip_row(self, x, y, w, h, items, theme='neutral', gap=10):
        n = len(items)
        cw = (w - gap * (n - 1)) / n
        for i, it in enumerate(items):
            t, s = (it, None) if isinstance(it, str) else it
            self.box(round(x + i * (cw + gap), 1), y, round(cw, 1), h, t, s, theme)
        return cw

    def render(self, name):
        head = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" '
                f'height="{self.h}" role="img" aria-label="{escape(self.label)}">',
                f'<title>{escape(self.label)}</title>',
                f'<style>{STYLE}</style>',
                '<defs>' + ''.join(self.markers.values()) + '</defs>',
                f'<rect x="0.5" y="0.5" width="{self.w - 1}" height="{self.h - 1}" rx="18" fill="#FFFFFF" stroke="{LINE}"/>']
        if self.title:
            head.append(f'<text x="36" y="46" class="title">{escape(self.title)}</text>')
        if self.subtitle:
            head.append(f'<text x="36" y="70" class="subtitle">{escape(self.subtitle)}</text>')
        (OUT / name).write_text('\n'.join(head + self.body + ['</svg>']) + '\n')
        print('wrote', name)


# =============================================================================
# 1. The serving stack: an operating system for inference
# =============================================================================
def serving_stack():
    s = SVG(1360, 1010, 'The LLM serving stack',
            'An operating system for inference: every layer is a choice, and the choices must fit together.',
            'Layered LLM serving stack: applications, access, serving control plane (Dynamo or llm-d), '
            'inference engines (TensorRT-LLM, vLLM, SGLang), model architectures, data movement, and '
            'hardware, with storage connected directly to GPUs and platform services alongside.')
    AX, AW = 36, 150            # OS-analogy margin
    MX, MW = 204, 850           # main stack
    RX, RW = 1074, 250          # side columns

    s.text(AX, 104, 'OS ANALOGY', 'h', fill=FAINT)

    rows = [
        # key, y, h, heading, theme, analogy
        ('apps', 116, 66, 'Applications', 'access', ['applications']),
        ('access', 194, 66, 'Access layer', 'access', ['shell &', 'system calls']),
        ('orch', 272, 176, 'Serving control plane', 'orch', ['scheduler &', 'process manager']),
        ('engine', 460, 124, 'Inference engines', 'engine', ['process runtime']),
        ('model', 596, 100, 'Model architectures', 'model', ['programs', '(workload shapes)']),
        ('runtime', 708, 100, 'Data movement & memory', 'runtime', ['drivers &', 'virtual memory']),
        ('hw', 820, 164, 'Hardware', 'hw', ['hardware']),
    ]
    for key, y, h, heading, theme, analogy in rows:
        s.line(AX, y, AX + AW - 16, y, LINE, 1)
        s.lines(AX, y + 22, analogy, 'note', lh=15)

    # Applications
    s.panel(MX, 116, MW, 66, 'Applications', 'access')
    s.chip_row(MX + 200, 128, MW - 214, 42,
               ['Chat assistants', 'Agents & tools', 'RAG & search', 'Batch & offline'])
    # Access
    s.panel(MX, 194, MW, 66, 'Access layer', 'access')
    s.chip_row(MX + 200, 206, MW - 214, 42,
               ['OpenAI-compatible API', 'AuthN/Z · quotas', 'TLS · rate limits'])

    # Serving control plane: two options
    s.panel(MX, 272, MW, 176, 'Serving control plane', 'orch', 'choose one')
    pw = (MW - 42) / 2
    for i, (name, tag, comps) in enumerate([
        ('NVIDIA Dynamo', 'engine-agnostic · Docker or Kubernetes',
         ['Frontend + KV router', 'Planner (SLO scaling)', 'KV block manager',
          'NIXL transfer', 'Discovery (etcd)', 'Operator · Grove']),
        ('llm-d', 'Kubernetes-native · Gateway API',
         ['Envoy gateway', 'Endpoint picker (EPP)', 'P/D routing sidecar',
          'InferencePool CRD', 'KV-cache indexer', 'Variant autoscaler'])]):
        px = MX + 14 + i * (pw + 14)
        s.rect(px, 304, pw, 132, '#FFFFFF', LAYER['orch'][1], 10, 1.2)
        s.text(px + 14, 326, name, 'lbl-lg', fill=LAYER['orch'][2])
        s.text(px + pw - 14, 326, tag, 'small', 'end')
        cw = (pw - 28 - 16) / 3
        for j, c in enumerate(comps):
            cx = px + 14 + (j % 3) * (cw + 8)
            cy = 340 + (j // 3) * 44
            s.rect(cx, cy, cw, 36, LAYER['orch'][0], LAYER['orch'][1], 8, 1)
            s.text(cx + cw / 2, cy + 22, c, 'sub', 'middle', fill=INK)

    # Engines
    s.panel(MX, 460, MW, 124, 'Inference engines', 'engine', 'one per worker')
    s.chip_row(MX + 14, 488, MW - 28, 56, [
        ('TensorRT-LLM', 'NVIDIA-optimized kernels · NVFP4'),
        ('vLLM', 'broad model & hardware support'),
        ('SGLang', 'RadixAttention · agentic workloads')], 'engine')
    s.text(MX + MW / 2, 570, 'shared techniques: continuous batching · paged KV cache · chunked prefill · '
           'prefix caching · speculative decoding', 'small', 'middle')

    # Models
    s.panel(MX, 596, MW, 100, 'Model architectures', 'model', 'decides KV size & parallelism')
    s.chip_row(MX + 14, 624, MW - 28, 56, [
        ('Dense', 'GQA attention'), ('MoE', 'sparse experts'), ('MLA', 'latent KV'),
        ('Hybrid', 'Mamba + attention'), ('Sliding window', 'bounded KV'),
        ('Multimodal', 'vision encoder')], 'model')

    # Runtime
    s.panel(MX, 708, MW, 100, 'Data movement & memory', 'runtime')
    s.chip_row(MX + 14, 736, MW - 28, 56, [
        ('NIXL', 'KV transfer API'), ('NCCL', 'TP/EP collectives'), ('UCX', 'RDMA transport'),
        ('GPUDirect RDMA', 'NIC ↔ GPU'), ('GPUDirect Storage', 'NVMe ↔ GPU'),
        ('KV cache manager', 'paging across tiers')], 'runtime')

    # Hardware
    s.panel(MX, 820, MW, 164, 'Hardware', 'hw')
    gw = (MW - 28 - 30) / 4
    gpus = [('H100 · H200', 'Hopper · 8-GPU HGX'), ('B200 · B300', 'Blackwell · 8-GPU HGX'),
            ('GB200 · GB300 NVL72', 'rack-scale NVLink'), ('Vera Rubin · Rubin CPX', 'next generation')]
    for i, (t, sub) in enumerate(gpus):
        s.box(MX + 14 + i * (gw + 10), 846, gw, 50, t, sub, 'hw')
    s.rect(MX + 14, 906, MW - 28, 30, '#E2E8F0', '#94A3B8', 7, 1)
    s.text(MX + MW / 2, 926, 'Scale-up fabric · NVLink / NVSwitch (inside a server or an NVL72 rack)',
           'sub', 'middle', fill=INK)
    s.rect(MX + 14, 944, MW - 28, 30, '#1E293B', '#1E293B', 7, 1)
    s.text(MX + MW / 2, 964, 'Scale-out fabric · InfiniBand · Spectrum-X Ethernet (RoCE) · ConnectX SuperNICs',
           'sub', 'middle', fill='#F8FAFC')
    # every GPU system attaches to both fabrics
    for i in range(4):
        cx = MX + 14 + i * (gw + 10) + gw / 2
        s.line(cx, 896, cx, 906, '#64748B', 1.4)
        s.line(cx - 40, 936, cx - 40, 944, '#64748B', 1.4)

    # Platform column
    s.panel(RX, 272, RW, 424, 'Platform & operations', 'platform')
    items = [('Kubernetes', 'scheduling · gang placement'),
             ('GPU Operator', 'drivers · device plugin · DCGM'),
             ('Network Operator', 'RDMA devices · SR-IOV'),
             ('Observability', 'TTFT · ITL · KV hit rate'),
             ('Security', 'mTLS · secrets · tenancy'),
             ('Model registry', 'pinned weights · revisions')]
    for i, (t, sub) in enumerate(items):
        s.box(RX + 14, 304 + i * 64, RW - 28, 54, t, sub, 'platform')

    # Storage column
    s.panel(RX, 708, RW, 276, 'Storage · KV tiers', 'storage')
    tiers = [('Host DRAM', 'G2 · offloaded KV blocks'),
             ('Local NVMe', 'G3 · warm prefixes'),
             ('Parallel FS / object', 'G4 · shared across nodes'),
             ('Model weights', 'read-only, pinned revision')]
    for i, (t, sub) in enumerate(tiers):
        s.box(RX + 14, 740 + i * 60, RW - 28, 50, t, sub, 'storage')
    # GPUDirect Storage: local NVMe straight into GPU memory, no CPU bounce buffer
    gx = MX + 14 + 3 * (gw + 10) + gw
    s.arrow([(gx, 871), (RX - 10, 871), (RX - 10, 825), (RX + 14, 825)], LAYER['storage'][2], 2.0, both=True)
    s.text(MX + MW - 14, 840, 'GPUDirect Storage to local NVMe', 'tiny', 'end', fill=LAYER['storage'][2], weight=700)

    s.render('serving-stack.svg')
    return s




# =============================================================================
# 2. Aggregated vs disaggregated: the one edge disaggregation adds
# =============================================================================
def timeline(s, x, y, w, segs, label=None):
    """segs: list of ('d'|'p', width). Draws a GPU-time strip."""
    s.line(x, y + 26, x + w, y + 26, FAINT, 1)
    cx = x
    for kind, sw in segs:
        if kind == 'd':
            s.rect(cx, y + 6, sw - 3, 16, LAYER['decode'][1], LAYER['decode'][1], 2, 0.5)
        elif kind == 'p':
            s.rect(cx, y + 6, sw - 3, 16, LAYER['prefill'][1], LAYER['prefill'][1], 2, 0.5)
        cx += sw
    if label:
        s.text(x, y + 42, label, 'tiny')


def agg_vs_disagg():
    s = SVG(1360, 720, 'Aggregated vs disaggregated serving',
            'Same GPUs, same model. Disaggregation adds one edge, the KV-cache transfer, and removes phase interference.',
            'Side-by-side comparison. Aggregated: a router sends whole requests to replicas that run prefill and decode '
            'on the same GPUs, so long prefills stall decoding. Disaggregated: prefill and decode run in separate pools '
            'and the KV cache moves between them over RDMA.')
    for side, px in (('agg', 36), ('dis', 694)):
        agg = side == 'agg'
        pw = 630
        s.rect(px, 96, pw, 600, '#FCFCFD', LINE, 14, 1.2)
        s.text(px + 20, 124, 'AGGREGATED' if agg else 'DISAGGREGATED', 'h', fill=MUTED)
        s.text(px + 20, 146, 'Replicated monolith' if agg else 'Phase-specialized services', 'lbl-lg')
        cx = px + pw / 2
        s.box(cx - 130, 170, 260, 48, 'Router', 'KV-aware · picks workers', 'orch')
        if agg:
            for i in range(2):
                bx = px + 30 + i * 300
                s.rect(bx, 270, 270, 250, '#FFFFFF', LAYER['neutral'][1], 12, 1.3)
                s.text(bx + 16, 294, f'Replica {i + 1}', 'lbl')
                s.text(bx + 254, 294, '8 GPUs · TP8', 'small', 'end')
                s.box(bx + 16, 308, 238, 44, 'Prefill', 'compute-bound', 'prefill')
                s.box(bx + 16, 360, 238, 44, 'Decode', 'memory-bandwidth-bound', 'decode')
                timeline(s, bx + 16, 440, 238, [('d', 18)] * 4 + [('p', 94)] + [('d', 18)] * 4, 'GPU time →')
                s.arrow([(cx, 218), (cx, 244), (bx + 135, 244), (bx + 135, 268)], MUTED, 1.6)
            s.text(cx - 150, 238, 'whole request', 'edge', 'end')
            # interference callout on replica 1 timeline
            s.line(px + 30 + 16 + 72, 440, px + 30 + 16 + 72 + 91, 440, ROSE, 2)
            s.text(px + 30 + 16 + 72 + 46, 434, 'decode stalls', 'tiny', 'middle', fill=ROSE, weight=700)
            facts = [('Scaling unit', 'a whole replica (prefill + decode together)'),
                     ('Between nodes', 'no KV movement, no RDMA needed'),
                     ('Weak spot', 'long prompts stall other users’ tokens (ITL spikes)'),
                     ('Best for', 'short prompts, simple operations, first baseline')]
        else:
            lx, rx = px + 30, px + pw - 30 - 240
            for bx, theme, name, sub in ((lx, 'prefill', 'Prefill pool', 'compute-bound'),
                                         (rx, 'decode', 'Decode pool', 'memory-bandwidth-bound')):
                fill, stroke, head = LAYER[theme]
                s.rect(bx, 270, 240, 250, fill, stroke, 12, 1.4)
                s.text(bx + 16, 294, name, 'lbl', fill=head)
                s.text(bx + 224, 294, sub, 'tiny', 'end')
                for j in range(2):
                    s.box(bx + 16, 308 + j * 50, 208, 40, f'Worker {j + 1} · 8 GPUs', None, 'neutral')
                s.rect(bx + 16, 408, 208, 22, '#FFFFFF', stroke, 8, 1, '4 3')
                s.text(bx + 120, 423, '+ add workers for this phase only', 'tiny', 'middle')
                segs = [('p', 50)] * 4 if theme == 'prefill' else [('d', 18)] * 11
                timeline(s, bx + 16, 440, 208, segs, 'GPU time →')
            # router -> prefill, decode -> router
            s.arrow([(cx - 60, 218), (cx - 60, 244), (lx + 120, 244), (lx + 120, 268)], MUTED, 1.6)
            s.text(lx + 128, 238, '① prompt', 'edge')
            s.arrow([(rx + 120, 268), (rx + 120, 244), (cx + 60, 244), (cx + 60, 220)], MUTED, 1.6)
            s.text(rx + 112, 238, '③ tokens', 'edge', 'end')
            # the added edge: KV transfer
            s.arrow([(lx + 240, 350), (rx, 350)], ROSE, 3.2)
            s.text(cx, 338, '② KV cache', 'edge-kv', 'middle')
            s.text(cx, 376, 'RDMA · NIXL', 'tiny', 'middle', fill=ROSE, weight=700)
            s.text(cx, 392, 'or NVLink', 'tiny', 'middle', fill=ROSE)
            facts = [('Scaling unit', 'each phase independently (P:D ratio)'),
                     ('Between nodes', 'KV cache per request: needs RDMA or NVLink'),
                     ('Strength', 'steady ITL; tune batch & parallelism per phase'),
                     ('Best for', 'long prompts, strict latency SLOs, large MoE')]
        for i, (k, v) in enumerate(facts):
            fy = 560 + i * 30
            s.line(px + 20, fy - 18, px + pw - 20, fy - 18, LINE, 1)
            s.text(px + 20, fy, k, 'lbl', size=12)
            s.text(px + 140, fy, v, 'sub')
    s.render('agg-vs-disagg.svg')


# =============================================================================
# 3. The microservices analogy
# =============================================================================
def microservices():
    s = SVG(1360, 800, 'Disaggregated serving is the microservices pattern for inference',
            'Split a monolith by resource profile, scale each part for its own traffic. The difference: the hand-off is gigabytes.',
            'Two by two comparison. A monolith maps to aggregated serving; microservices map to disaggregated serving. '
            'API gateway maps to the router, the service registry to etcd or the InferencePool, the autoscaler to the '
            'Planner. Unlike microservices, prefill hands decode gigabytes of KV cache over RDMA.')
    cols = [(36, 'CLASSIC APPLICATION'), (714, 'LLM INFERENCE')]
    for x, h in cols:
        s.text(x + 305, 104, h, 'h', 'middle', fill=MUTED)
    # row 1: monolith vs aggregated
    def row_frame(x, y, h, title):
        s.rect(x, y, 610, h, '#FCFCFD', LINE, 14, 1.2)
        s.text(x + 18, y + 26, title, 'lbl-lg')
    row_frame(36, 118, 250, 'Monolith')
    row_frame(714, 118, 250, 'Aggregated serving')
    s.box(36 + 205, 158, 200, 40, 'Load balancer', None, 'orch')
    s.box(714 + 205, 158, 200, 40, 'Router', None, 'orch')
    for i in range(2):
        bx = 36 + 40 + i * 290
        s.rect(bx, 222, 240, 116, '#FFFFFF', LAYER['neutral'][1], 10, 1.2)
        s.text(bx + 12, 242, f'Instance {i + 1}', 'small')
        for j, m in enumerate(['UI', 'Orders', 'Search', 'Payments']):
            s.box(bx + 12 + (j % 2) * 112, 252 + (j // 2) * 40, 104, 32, m, None, 'access')
        s.arrow([(36 + 305, 198), (36 + 305, 210), (bx + 120, 210), (bx + 120, 220)], MUTED, 1.4)
        rx = 714 + 40 + i * 290
        s.rect(rx, 222, 240, 116, '#FFFFFF', LAYER['neutral'][1], 10, 1.2)
        s.text(rx + 12, 242, f'Replica {i + 1} · 8 GPUs', 'small')
        s.box(rx + 12, 252, 216, 34, 'Prefill', None, 'prefill')
        s.box(rx + 12, 292, 216, 34, 'Decode', None, 'decode')
        s.arrow([(714 + 305, 198), (714 + 305, 210), (rx + 120, 210), (rx + 120, 220)], MUTED, 1.4)
    s.text(680, 250, '≈', 'title', 'middle', fill=FAINT)

    # row 2: microservices vs disaggregated
    row_frame(36, 388, 300, 'Microservices')
    row_frame(714, 388, 300, 'Disaggregated serving')
    for x, gw, a, b, reg, auto, edge, kv in (
            (36, 'API gateway', ('Search service', 'read-heavy · 3 replicas', 'access'),
             ('Orders service', 'write-heavy · 1 replica', 'access'), 'Service registry', 'Autoscaler (HPA)',
             'JSON · kilobytes', False),
            (714, 'Frontend / router', ('Prefill service', 'compute-bound · 3 workers', 'prefill'),
             ('Decode service', 'bandwidth-bound · 2 workers', 'decode'), 'etcd / InferencePool', 'Planner / autoscaler',
             'KV cache · gigabytes', True)):
        s.box(x + 205, 428, 200, 40, gw, None, 'orch')
        for k, (name, sub, th) in enumerate((a, b)):
            bx = x + 30 + k * 330
            fill, stroke, head = LAYER[th]
            for d in (8, 4, 0):                      # stacked replicas
                s.rect(bx + d, 510 - d, 220, 60, fill, stroke, 10, 1.2)
            s.text(bx + 110, 534, name, 'lbl', 'middle', fill=head if th != 'access' else INK)
            s.text(bx + 110, 552, sub, 'sub', 'middle')
            s.arrow([(x + 305, 468), (x + 305, 484), (bx + 110, 484), (bx + 110, 500)], MUTED, 1.4)
        color = ROSE if kv else MUTED
        s.arrow([(x + 258, 540), (x + 352, 540)], color, 3 if kv else 1.6)
        s.text(x + 305, 596, edge, 'edge-kv' if kv else 'edge', 'middle')
        s.text(x + 305, 612, 'RDMA · NIXL' if kv else 'HTTP / gRPC', 'tiny', 'middle', fill=color)
        s.box(x + 30, 628, 250, 40, reg, 'discovery', 'platform')
        s.box(x + 330, 628, 250, 40, auto, 'scales each service', 'platform')
    s.text(680, 540, '≈', 'title', 'middle', fill=FAINT)

    # bottom takeaway
    s.rect(36, 708, 1288, 64, ROSE_BG, '#FDA4AF', 12, 1.2)
    s.text(56, 734, 'What carries over:', 'lbl', fill=ROSE)
    s.text(196, 734, 'split by resource profile · scale each part for its own traffic · a gateway routes · a registry discovers · '
           'an autoscaler right-sizes.', 'sub', fill=INK)
    s.text(56, 756, 'What does not:', 'lbl', fill=ROSE)
    s.text(196, 756, 'services exchange kilobytes; prefill hands decode gigabytes of state per request, so the GPU fabric '
           '(RDMA, NVLink) becomes part of the architecture.', 'sub', fill=INK)
    s.render('microservices-analogy.svg')


# =============================================================================
# 4. Disaggregated request lifecycle (sequence)
# =============================================================================
def request_flow():
    s = SVG(1360, 800, 'Life of a request in disaggregated serving',
            'vLLM + NIXL flow under Dynamo. Decode pulls the KV cache directly from prefill GPU memory.',
            'Sequence diagram with four lanes: client, frontend and router, prefill worker, decode worker. The router '
            'picks workers, prefill computes the KV cache, decode reads the KV blocks over RDMA and streams tokens back.')
    lanes = [('Client', 'application', 'access', 170), ('Frontend + router', 'OpenAI API · KV-aware', 'orch', 490),
             ('Prefill worker', 'GPU pool A', 'prefill', 830), ('Decode worker', 'GPU pool B', 'decode', 1170)]
    for name, sub, th, x in lanes:
        s.box(x - 120, 96, 240, 52, name, sub, th)
        s.line(x, 148, x, 716, FAINT, 1.2, '4 4')
    X = {k: v[3] for k, v in zip(['c', 'f', 'p', 'd'], lanes)}

    def msg(n, y, a, b, label, color=MUTED, sw=1.6, cls='edge', dy=-8):
        s.arrow([(X[a] + (6 if X[b] > X[a] else -6), y), (X[b] + (-8 if X[b] > X[a] else 8), y)], color, sw)
        mx = (X[a] + X[b]) / 2
        s.text(mx, y + dy, label, cls, 'middle', fill=None if color == MUTED else color)
        s.step(min(X[a], X[b]) + 22, y - 14 if dy < 0 else y + 14, n, ROSE if color == ROSE else INK)

    def act(lane, y, h, theme, label, sub, side='right'):
        fill, stroke, head = LAYER[theme]
        s.rect(X[lane] - 8, y, 16, h, fill, stroke, 3, 1.3)
        tx = X[lane] + 20 if side == 'right' else X[lane] - 20
        anc = 'start' if side == 'right' else 'end'
        s.text(tx, y + h / 2 - 2, label, 'lbl', anc, fill=head if theme != 'neutral' else INK, size=12)
        s.text(tx, y + h / 2 + 14, sub, 'sub', anc)

    msg(1, 196, 'c', 'f', 'POST /v1/chat/completions')
    act('f', 214, 46, 'orch', 'Tokenize · template · route', 'pick P and D by KV overlap and load')
    msg(2, 300, 'f', 'p', 'prefill request (whole prompt)')
    act('p', 316, 66, 'prefill', 'Compute KV for every prompt token', 'compute-bound · TTFT lives here')
    msg(3, 420, 'p', 'f', 'first token + KV block handles')
    msg(4, 476, 'f', 'd', 'decode request + handles')
    msg(5, 532, 'd', 'p', 'RDMA read of KV blocks · NIXL · GPUDirect', ROSE, 3, 'edge-kv')
    act('d', 552, 76, 'decode', 'Generate tokens', 'one step per token · ITL lives here', 'left')
    msg(6, 672, 'd', 'c', 'stream tokens (SSE) via the frontend')

    s.rect(36, 730, 1288, 50, '#F8FAFC', LINE, 10, 1)
    s.text(56, 752, 'TTFT', 'lbl', size=12)
    s.text(100, 752, '= queueing + prefill (step 2) + KV transfer (step 5) + first decode step', 'sub')
    s.text(56, 770, 'ITL', 'lbl', size=12)
    s.text(100, 770, '= one decode step; other users’ prefills run on other GPUs and no longer stall it', 'sub')
    s.text(1304, 761, 'SGLang: decode handshakes with prefill’s bootstrap server (:8998), prefill pushes KV', 'note', 'end')
    s.render('disagg-request-flow.svg')


# =============================================================================
# 5. KV-transfer data path: GPUDirect RDMA over rail-optimized fabric
# =============================================================================
def kv_datapath():
    s = SVG(1360, 720, 'How the KV cache crosses nodes',
            'Each GPU sends its own KV shard through its own NIC and rail. CPU and host memory stay off the path.',
            'Two 8-GPU nodes. Within each node GPUs share an NVLink switch for tensor parallelism. Each GPU connects '
            'through a PCIe switch to its own NIC; eight InfiniBand rails connect NIC i on the prefill node to NIC i '
            'on the decode node. The CPU is not on the KV path.')
    nodes = [(36, 'Node A · prefill', 'prefill', False), (824, 'Node B · decode', 'decode', True)]
    ys = [134 + i * 50 for i in range(8)]
    for nx, title, th, mirror in nodes:
        fill, stroke, head = LAYER[th]
        s.rect(nx, 96, 500, 598, '#FCFCFD', stroke, 14, 1.4)
        s.text(nx + 20, 122, title, 'lbl-lg', fill=head)
        # columns (mirrored for node B)
        def X(off, w):
            return nx + 500 - off - w if mirror else nx + off
        sw_x, gpu_x, pcie_x, nic_x = X(20, 34), X(74, 128), X(242, 84), X(356, 124)
        s.rect(sw_x, ys[0] + 4, 34, ys[-1] - ys[0] + 32, '#E2E8F0', '#94A3B8', 8, 1)
        s.text(sw_x + 21, (ys[0] + ys[-1]) / 2 + 20, 'NVLink / NVSwitch · TP8', 'tiny',
               'middle', fill=INK, weight=600, rotate=-90)
        for i, y in enumerate(ys):
            s.line(sw_x + 34 if not mirror else sw_x, y + 20, gpu_x if not mirror else gpu_x + 128, y + 20, '#94A3B8', 1.2)
            s.box(gpu_x, y + 2, 128, 36, f'GPU {i}', f'KV shard {i}' if False else None, th, rx=7, sw=1.2)
            s.box(pcie_x, y + 6, 84, 28, 'PCIe switch', None, 'neutral', rx=6, sw=1)
            s.box(nic_x, y + 4, 124, 32, f'NIC {i} · 800G', None, 'hw', rx=6, sw=1.1)
            # GPU -> PCIe -> NIC (the data path)
            a, b = (gpu_x + 128, pcie_x) if not mirror else (pcie_x + 84, gpu_x)
            c, d = (pcie_x + 84, nic_x) if not mirror else (nic_x + 124, pcie_x)
            s.line(a, y + 20, b, y + 20, ROSE, 1.8)
            s.line(c, y + 20, d, y + 20, ROSE, 1.8)
        # CPU off path
        cpu_x = X(242, 238)
        s.rect(cpu_x, 560, 238, 64, '#FFFFFF', '#94A3B8', 10, 1.2, '5 4')
        s.text(cpu_x + 119, 586, 'CPU · host DRAM', 'lbl', 'middle', size=12)
        s.text(cpu_x + 119, 604, 'not on the KV path (no bounce copy)', 'sub', 'middle')
        s.line(pcie_x + 42, ys[-1] + 34, pcie_x + 42, 560, '#CBD5E1', 1.2, '3 3')
        s.text(nx + 250, 660, 'KV cache is sharded by TP: GPU i holds KV shard i', 'note', 'middle')
    # fabric
    s.rect(566, 96, 228, 598, '#1E293B', '#1E293B', 14, 1)
    s.text(680, 122, 'SCALE-OUT FABRIC', 'h', 'middle', fill='#CBD5E1')
    s.text(680, 140, 'InfiniBand / RoCE · rail-optimized', 'tiny', 'middle', fill='#94A3B8')
    for i, y in enumerate(ys):
        s.arrow([(36 + 480, y + 20), (824 + 20, y + 20)], ROSE, 2.2)
        s.rect(640, y + 11, 80, 18, '#1E293B', '#1E293B', 4, 0)
        s.text(680, y + 24, f'rail {i}', 'tiny', 'middle', fill='#F8FAFC', weight=600)
    s.text(680, 560, 'GPU i → NIC i →', 'small', 'middle', fill='#E2E8F0')
    s.text(680, 578, 'rail i → NIC i → GPU i', 'small', 'middle', fill='#E2E8F0')
    s.text(680, 614, '8 rails in parallel', 'lbl', 'middle', fill='#FDA4AF', size=12)
    s.text(680, 632, '≈ 8 × 100 GB/s line rate', 'tiny', 'middle', fill='#CBD5E1')
    s.render('kv-transfer-datapath.svg')


# =============================================================================
# 6. Scale-out servers vs scale-up racks
# =============================================================================
def hardware_scaling():
    s = SVG(1360, 740, 'Scale-out servers vs scale-up racks',
            'Where the KV cache moves decides how far disaggregation and expert parallelism can stretch.',
            'Left: two 8-GPU servers, each its own NVLink domain, connected by an InfiniBand or Ethernet fabric; '
            'KV moves between servers over RDMA. Right: a rack-scale NVLink domain of 72 GPUs where prefill and decode '
            'GPUs exchange KV over NVLink and wide expert parallelism spans the rack.')
    # left panel
    s.rect(36, 96, 620, 620, '#FCFCFD', LINE, 14, 1.2)
    s.text(56, 124, 'SCALE-OUT', 'h', fill=MUTED)
    s.text(56, 146, '8-GPU servers · HGX H200 / B200 / B300', 'lbl-lg')
    for k, (sx, th, role) in enumerate(((66, 'prefill', 'prefill'), (366, 'decode', 'decode'))):
        fill, stroke, head = LAYER[th]
        s.rect(sx, 176, 260, 230, '#FFFFFF', '#94A3B8', 12, 1.3)
        s.text(sx + 14, 198, f'Server {k + 1} · {role}', 'lbl', fill=head)
        s.rect(sx + 14, 210, 232, 124, '#F1F5F9', '#94A3B8', 10, 1, '5 3')
        s.text(sx + 130, 226, 'NVLink domain · 8 GPUs', 'tiny', 'middle', fill=INK, weight=600)
        for i in range(8):
            gx, gy = sx + 26 + (i % 4) * 54, 236 + (i // 4) * 46
            s.rect(gx, gy, 46, 38, fill, stroke, 6, 1.1)
            s.text(gx + 23, gy + 23, f'GPU', 'tiny', 'middle', fill=head, weight=600)
        s.rect(sx + 14, 346, 232, 44, LAYER['hw'][0], LAYER['hw'][1], 8, 1)
        s.text(sx + 130, 373, '8 × NIC (one per GPU)', 'sub', 'middle', fill=INK)
        s.line(sx + 130, 390, sx + 130, 440, '#475569', 1.6)
    s.rect(66, 440, 560, 40, '#1E293B', '#1E293B', 10, 1)
    s.text(346, 465, 'InfiniBand / Spectrum-X Ethernet fabric', 'sub', 'middle', fill='#F8FAFC')
    s.arrow([(326, 290), (366, 290)], ROSE, 3)
    s.text(346, 278, 'KV', 'edge-kv', 'middle')
    s.text(346, 318, 'RDMA', 'tiny', 'middle', fill=ROSE, weight=700)
    fits = [('TP / EP', 'up to 8 GPUs, inside one server'),
            ('P/D transfer', 'across the fabric, GPUDirect RDMA'),
            ('Grows by', 'adding servers; fabric bandwidth per GPU'),
            ('Reference here', '2 × 8 × B300 (deployments 01–04)')]
    for i, (k, v) in enumerate(fits):
        fy = 540 + i * 36
        s.line(56, fy - 22, 636, fy - 22, LINE, 1)
        s.text(56, fy, k, 'lbl', size=12)
        s.text(196, fy, v, 'sub')

    # right panel
    s.rect(684, 96, 640, 620, '#FCFCFD', LINE, 14, 1.2)
    s.text(704, 124, 'SCALE-UP', 'h', fill=MUTED)
    s.text(704, 146, 'Rack-scale NVLink · GB200 / GB300 NVL72, Vera Rubin', 'lbl-lg')
    s.rect(714, 176, 580, 312, '#F1F5F9', '#94A3B8', 12, 1.3, '5 3')
    s.text(1004, 198, 'One NVLink domain · 72 GPUs', 'tiny', 'middle', fill=INK, weight=600)
    for r in range(6):
        for c in range(12):
            th = 'prefill' if r < 2 else 'decode'
            fill, stroke, head = LAYER[th]
            gx = 734 + c * 42
            gy = 212 + r * 40 + (32 if r >= 3 else 0)
            s.rect(gx, gy, 34, 32, fill, stroke, 5, 1)
    s.rect(734, 334, 496, 22, '#CBD5E1', '#94A3B8', 5, 1)
    s.text(982, 349, 'NVLink switch trays · all-to-all', 'tiny', 'middle', fill=INK, weight=600)
    # KV from prefill rows to decode rows, drawn beside the grid
    s.arrow([(1234, 244), (1256, 244), (1256, 416), (1234, 416)], ROSE, 3)
    s.text(1272, 330, 'KV over NVLink', 'edge-kv', 'middle', rotate=90)
    s.text(734, 510, 'prefill GPUs (top two rows) · decode GPUs (other rows) · wide EP spans all 72', 'tiny')
    s.rect(714, 522, 580, 36, '#1E293B', '#1E293B', 10, 1)
    s.text(1004, 545, 'Scale-out fabric to other racks', 'sub', 'middle', fill='#F8FAFC')
    fits = [('TP / EP', 'wide EP across up to 72 GPUs (large MoE decode)'),
            ('P/D transfer', 'over NVLink inside the rack; RDMA between racks'),
            ('Grows by', 'adding racks; NVLink bandwidth per GPU is several × a NIC')]
    for i, (k, v) in enumerate(fits):
        fy = 612 + i * 36
        s.line(704, fy - 22, 1304, fy - 22, LINE, 1)
        s.text(704, fy, k, 'lbl', size=12)
        s.text(844, fy, v, 'sub')
    s.render('hardware-scaling.svg')


# =============================================================================
# 7. KV-cache memory hierarchy and GPUDirect Storage
# =============================================================================
def kv_hierarchy():
    s = SVG(1360, 720, 'KV cache as virtual memory',
            'Evict down the hierarchy instead of discarding; reload instead of recomputing. GPUDirect Storage removes the CPU detour.',
            'Left: four KV tiers from GPU memory to shared storage, capacity growing and bandwidth falling, with offload '
            'and onboard arrows. Right: without GPUDirect Storage, NVMe data goes through a CPU bounce buffer before '
            'reaching the GPU; with it, the NVMe drive writes directly into GPU memory through the PCIe switch.')
    tiers = [('G1 · GPU HBM', 'active sequences', 'smallest · fastest · per worker', 'decode', 300),
             ('G2 · Host DRAM', 'hot, recently evicted prefixes', 'larger · PCIe / C2C · per node', 'runtime', 400),
             ('G3 · Local NVMe', 'warm sessions and documents', '10× capacity · GPUDirect Storage · per node', 'storage', 500),
             ('G4 · Shared storage', 'prefixes reusable by any worker', 'largest · over RDMA · cluster-wide', 'hw', 600)]
    cx = 36 + 360
    for i, (name, what, props, th, w) in enumerate(tiers):
        y = 110 + i * 120
        fill, stroke, head = LAYER[th]
        s.rect(cx - w / 2, y, w, 84, fill, stroke, 12, 1.4)
        s.text(cx, y + 30, name, 'lbl-lg', 'middle', fill=head)
        s.text(cx, y + 50, what, 'sub', 'middle', fill=INK)
        s.text(cx, y + 68, props, 'small', 'middle')
        if i < 3:
            s.arrow([(cx - 60, y + 86), (cx - 60, y + 116)], MUTED, 1.6)
            s.arrow([(cx + 60, y + 116), (cx + 60, y + 86)], MUTED, 1.6)
            s.text(cx - 70, y + 106, 'offload on eviction', 'tiny', 'end')
            s.text(cx + 70, y + 106, 'onboard on cache hit', 'tiny')
    s.text(cx, 606, 'Reuse wins when reload time < recompute (prefill) time.', 'lbl', 'middle', size=12)
    s.text(cx, 624, 'The router must see all tiers to route to the worker holding the longest prefix.', 'sub', 'middle')

    # right: without vs with GDS
    rx = 800
    for k, (title, gds) in enumerate((('Without GPUDirect Storage', False), ('With GPUDirect Storage', True))):
        y = 104 + k * 300
        s.rect(rx, y, 524, 276, '#FCFCFD', ROSE if gds else LINE, 14, 1.4 if gds else 1.2)
        s.text(rx + 20, y + 28, title, 'lbl-lg', fill=ROSE if gds else INK)
        s.box(rx + 182, y + 50, 160, 44, 'CPU · DRAM', 'bounce buffer' if not gds else 'not involved',
              'neutral', dash=None if not gds else '5 4')
        s.box(rx + 182, y + 132, 160, 40, 'PCIe switch', None, 'hw')
        s.box(rx + 30, y + 206, 150, 46, 'NVMe drive', 'KV blocks', 'storage')
        s.box(rx + 344, y + 206, 150, 46, 'GPU HBM', 'decode / prefill', 'decode')
        s.line(rx + 262, y + 94, rx + 262, y + 132, '#CBD5E1', 1.4)
        if not gds:
            s.arrow([(rx + 105, y + 206), (rx + 105, y + 152), (rx + 182, y + 152)], MUTED, 1.8)
            s.arrow([(rx + 240, y + 132), (rx + 240, y + 96)], MUTED, 1.8)
            s.text(rx + 232, y + 118, '① DMA to host', 'edge', 'end')
            s.arrow([(rx + 284, y + 96), (rx + 284, y + 132)], MUTED, 1.8)
            s.text(rx + 292, y + 118, '② copy to GPU', 'edge')
            s.arrow([(rx + 342, y + 152), (rx + 419, y + 152), (rx + 419, y + 204)], MUTED, 1.8)
            s.text(rx + 262, y + 196, '2 transfers · CPU cycles · host bandwidth', 'tiny', 'middle')
        else:
            s.arrow([(rx + 105, y + 206), (rx + 105, y + 152), (rx + 182, y + 152)], ROSE, 2.6)
            s.arrow([(rx + 342, y + 152), (rx + 419, y + 152), (rx + 419, y + 204)], ROSE, 2.6)
            s.text(rx + 262, y + 196, '1 DMA straight into GPU memory (cuFile / NIXL GDS)', 'tiny', 'middle',
                   fill=ROSE, weight=700)
    s.render('kv-cache-hierarchy.svg')


# =============================================================================
# 8. Orchestration layer: Dynamo vs llm-d
# =============================================================================
def orchestrators():
    s = SVG(1360, 800, 'Two ways to run the serving control plane',
            'Same engines, same NIXL transfer. They differ in where routing decisions and P/D coordination live.',
            'Left: NVIDIA Dynamo. Requests go to a frontend with a KV router that dispatches prefill and decode to '
            'workers; etcd discovery, the Planner and the KV block manager support it. Right: llm-d. Requests go through '
            'an Envoy gateway that asks the endpoint picker for a pod; a routing sidecar on the decode pod coordinates '
            'prefill. Kubernetes provides discovery through the InferencePool.')
    for k, px in enumerate((36, 694)):
        dyn = k == 0
        pw = 630
        s.rect(px, 96, pw, 680, '#FCFCFD', LINE, 14, 1.2)
        s.text(px + 20, 124, 'NVIDIA DYNAMO' if dyn else 'LLM-D', 'h', fill=LAYER['orch'][2])
        s.text(px + 20, 146, 'Engine-agnostic runtime · Docker or Kubernetes' if dyn else
               'Kubernetes-native · Gateway API Inference Extension', 'lbl-lg')
        cx = px + pw / 2
        s.box(cx - 90, 166, 180, 36, 'Client', None, 'access')
        s.arrow([(cx, 202), (cx, 222)], MUTED, 1.6)
        if dyn:
            s.box(cx - 170, 224, 340, 50, 'Frontend', 'OpenAI API · tokenizer · chat template', 'orch')
            s.arrow([(cx, 274), (cx, 294)], MUTED, 1.6)
            s.box(cx - 170, 296, 340, 50, 'KV router', 'global prefix index from worker KV events', 'orch')
            s.rect(cx - 190, 216, 380, 140, 'none', ROSE, 12, 1.6, '6 4')
            s.text(cx + 196, 232, 'P/D coordination', 'tiny', 'start', fill=ROSE, weight=700)
            s.text(cx + 196, 246, 'lives here', 'tiny', 'start', fill=ROSE)
            s.arrow([(cx - 60, 346), (cx - 60, 372), (px + 150, 372), (px + 150, 398)], MUTED, 1.6)
            s.arrow([(cx + 60, 346), (cx + 60, 372), (px + pw - 150, 372), (px + pw - 150, 398)], MUTED, 1.6)
            s.text(px + 158, 390, '① prefill', 'edge')
            s.text(px + pw - 158, 390, '② decode', 'edge', 'end')
            workers = (('Prefill workers', 'prefill'), ('Decode workers', 'decode'))
            sub = 'dynamo.vllm · .sglang · .trtllm'
        else:
            s.box(cx - 170, 224, 250, 50, 'Gateway', 'Envoy + inference extension', 'orch')
            s.box(cx + 110, 224, 170, 50, 'Endpoint picker', 'prefix · load · P/D', 'orch')
            s.arrow([(cx + 80, 249), (cx + 108, 249)], MUTED, 1.4, both=True)
            s.text(cx + 94, 290, 'which pods?', 'tiny', 'middle')
            s.arrow([(cx - 45, 274), (cx - 45, 300), (px + pw - 150, 300), (px + pw - 150, 398)], MUTED, 1.6)
            s.text(px + pw - 158, 318, '① to decode pod', 'edge', 'end')
            workers = (('Prefill pod', 'prefill'), ('Decode pod', 'decode'))
            sub = 'vllm serve · sglang'
        # worker pools
        for j, (name, th) in enumerate(workers):
            bx = px + 30 if j == 0 else px + pw - 270
            fill, stroke, head = LAYER[th]
            s.rect(bx, 400, 240, 150, fill, stroke, 12, 1.4)
            s.text(bx + 16, 424, name, 'lbl', fill=head)
            if not dyn and th == 'decode':
                s.box(bx + 16, 436, 208, 40, 'Routing sidecar', 'P/D coordination', 'neutral')
                s.rect(bx + 10, 430, 220, 52, 'none', ROSE, 10, 1.6, '6 4')
                s.box(bx + 16, 490, 208, 44, 'vLLM decode', None, 'decode')
                s.arrow([(bx + 16, 456), (px + 272, 456)], MUTED, 1.6)
                s.text((bx + px + 272) / 2 + 8, 448, '② prefill first', 'edge', 'middle')
            else:
                for q in range(2):
                    s.box(bx + 16, 436 + q * 50, 208, 40, f'{"Prefill" if th == "prefill" else "Decode"} · 8 GPUs', sub if q == 0 else None, 'neutral')
        # KV transfer
        s.arrow([(px + 270, 520), (px + pw - 270, 520)], ROSE, 3)
        s.text(cx, 510, 'KV cache', 'edge-kv', 'middle')
        s.text(cx, 538, 'NIXL · RDMA', 'tiny', 'middle', fill=ROSE, weight=700)
        # supporting services
        s.text(px + 20, 588, 'SUPPORTING SERVICES', 'h', fill=MUTED)
        svc = ([('Discovery', 'etcd'), ('Planner', 'SLO-driven P:D scaling'), ('KV block manager', 'G1–G4 tiers'),
                ('Operator · Grove', 'K8s lifecycle, gang scheduling')] if dyn else
               [('Discovery', 'InferencePool · labels'), ('Variant autoscaler', 'per-role scaling'),
                ('KV-cache indexer', 'LMCache tiering'), ('Helm · Kustomize', 'well-lit-path guides')])
        for q, (t, sb) in enumerate(svc):
            s.box(px + 20 + (q % 2) * 300, 600 + (q // 2) * 60, 290, 50, t, sb, 'platform')
        s.text(px + 20, 740, 'Engines: vLLM · SGLang · TensorRT-LLM' if dyn else 'Engines: vLLM (primary) · SGLang',
               'sub', fill=INK)
        s.text(px + 20, 758, 'Deploy: Docker, Kubernetes (plain or operator)' if dyn else 'Deploy: Kubernetes only',
               'sub', fill=INK)
    s.render('orchestrators.svg')


# =============================================================================
# 9. Model architectures and what they mean for serving
# =============================================================================
def model_architectures():
    s = SVG(1360, 700, 'Model architecture decides the serving design',
            'What grows with context, what disaggregation must move, and which parallelism fits.',
            'Five model families drawn as layer stacks: dense attention, mixture of experts, multi-head latent attention, '
            'hybrid Mamba-attention, and sliding-window attention, with the relative KV cache per token and the '
            'serving implications of each.')
    cols = [
        ('Dense (GQA)', 'Llama 3 · Qwen3 dense', [('attn', 'Attention'), ('attn', 'Attention'), ('attn', 'Attention'), ('attn', 'Attention')], 1.0, 'full · every layer',
         ['KV of every layer', 'TP inside NVLink', 'simplest to serve']),
        ('MoE', 'Qwen3 MoE · gpt-oss · Mixtral', [('moe', 'Attention'), ('moe', 'Attention'), ('moe', 'Attention'), ('moe', 'Attention')], 1.0, 'same as dense',
         ['KV only (experts are weights)', 'EP for experts, TP/DP attention', 'decode loves wide EP']),
        ('MLA', 'DeepSeek V3/R1 · Kimi K2', [('mla', 'Latent attn'), ('mla', 'Latent attn'), ('mla', 'Latent attn'), ('mla', 'Latent attn')], 0.3, 'compressed latent',
         ['small latent KV per layer', 'DP attention + wide EP', 'cheap P/D transfer']),
        ('Hybrid SSM', 'Nemotron 3 · Nemotron-H · Jamba', [('ssm', 'Mamba'), ('ssm', 'Mamba'), ('attn', 'Attention'), ('ssm', 'Mamba')], 0.35, 'few layers + fixed state',
         ['KV of attention layers', '+ fixed Mamba state per seq', 'prefix cache at block edges']),
        ('Sliding window', 'gpt-oss · Gemma 3', [('swa', 'Local attn'), ('swa', 'Local attn'), ('attn', 'Global attn'), ('swa', 'Local attn')], 0.45, 'bounded by window',
         ['window KV + global layers', 'TP inside NVLink', 'long context stays cheap']),
    ]
    cw, gap, x0 = 240, 16, 48
    for i, (name, ex, layers, kv, kvlbl, impl) in enumerate(cols):
        x = x0 + i * (cw + gap)
        s.rect(x, 96, cw, 540, '#FCFCFD', LINE, 14, 1.2)
        s.text(x + cw / 2, 124, name, 'lbl-lg', 'middle', fill=LAYER['model'][2])
        s.text(x + cw / 2, 142, ex, 'small', 'middle')
        # layer stack
        for j, (kind, lab) in enumerate(layers):
            y = 164 + j * 58
            s.rect(x + 14, y, cw - 28, 48, '#FFFFFF', '#E2E8F0', 8, 1)
            if kind == 'ssm':
                s.box(x + 22, y + 7, 116, 34, lab, None, 'runtime', rx=6, sw=1)
                s.rect(x + 150, y + 12, 24, 24, LAYER['runtime'][1], LAYER['runtime'][2], 4, 1)
                s.text(x + 182, y + 29, 'state', 'tiny')
            else:
                label = lab
                s.box(x + 22, y + 7, 100 if kind in ('moe', 'mla') else 116, 34, label, None, 'engine', rx=6, sw=1)
                if kind in ('moe', 'mla'):
                    for e in range(6):
                        ex_ = x + 130 + (e % 3) * 16
                        ey = y + 9 + (e // 3) * 16
                        on = e in (1, 3)
                        s.rect(ex_, ey, 13, 13, LAYER['model'][1] if on else '#FFFFFF', LAYER['model'][1], 2, 1)
                # KV marker sized by relative KV
                full = kind == 'attn' and name != 'Sliding window' or kind == 'moe'
                if kind == 'attn' and name == 'Sliding window':
                    full = True
                kvw = 34 if full else 22
                kx = x + cw - 22 - kvw
                s.rect(kx, y + 14, kvw, 20, ROSE_BG, ROSE, 4, 1.2)
                s.text(kx + kvw / 2, y + 28, 'KV' if full else 'kv', 'tiny', 'middle', fill=ROSE, weight=700)
        s.text(x + cw / 2, 408, 'repeated × N layers', 'tiny', 'middle')
        # KV per token bar
        s.text(x + 16, 444, 'KV PER TOKEN', 'h', fill=MUTED)
        s.rect(x + 16, 454, cw - 32, 14, '#F1F5F9', '#E2E8F0', 7, 1)
        s.rect(x + 16, 454, (cw - 32) * kv, 14, ROSE, ROSE, 7, 0)
        s.text(x + 16, 486, kvlbl, 'sub', fill=INK)
        # implications
        s.text(x + 16, 524, 'SERVING IMPLICATIONS', 'h', fill=MUTED)
        for j, line in enumerate(impl):
            s.circle(x + 20, 546 + j * 26, 3, LAYER['model'][1])
            s.text(x + 30, 550 + j * 26, line, 'sub', fill=INK)
    s.text(680, 668, 'Bars are illustrative relative sizes, not measurements. KV per token = 2 × layers × KV heads × head dim × bytes for attention layers.',
           'note', 'middle')
    s.render('model-architectures.svg')


# =============================================================================
# 10. Reference lab topology used by deploy/
# =============================================================================
def reference_topology():
    s = SVG(1360, 660, 'Reference deployment topology',
            'Two 8 × B300 servers. Control traffic uses Ethernet; KV cache uses the InfiniBand rails (disaggregated only).',
            'Two GPU servers. Node A runs etcd, the Dynamo frontend and one GPU worker; Node B runs one GPU worker. Both '
            'attach to a control network over Ethernet and to eight InfiniBand rails that carry the KV cache in '
            'disaggregated mode. Model weights sit on local NVMe on each node.')
    s.box(36, 250, 170, 70, 'Clients', 'benchmark · apps', 'access')
    for k, (nx, title) in enumerate(((256, 'Node A · <B300_NODE_A_IP>'), (820, 'Node B · <B300_NODE_B_IP>'))):
        s.rect(nx, 96, 504, 390, '#FCFCFD', '#94A3B8', 14, 1.3)
        s.text(nx + 20, 122, title, 'lbl-lg')
        s.text(nx + 484, 122, '8 × B300 · NVLink', 'small', 'end')
        if k == 0:
            s.box(nx + 20, 140, 150, 56, 'etcd', ':2379 discovery', 'orch')
            s.box(nx + 186, 140, 298, 56, 'Dynamo frontend', ':8000 OpenAI API · KV router', 'orch')
        wy = 216 if k == 0 else 140
        wh = 150 if k == 0 else 226
        s.rect(nx + 20, wy, 464, wh, '#FFFFFF', '#CBD5E1', 12, 1.2)
        s.text(nx + 36, wy + 24, 'GPU worker · 8 GPUs · TP8', 'lbl')
        s.text(nx + 468, wy + 24, ':8081 health · metrics', 'small', 'end')
        s.box(nx + 36, wy + 40, 208, 50, 'Aggregated', f'replica {k + 1}', 'neutral')
        s.box(nx + 260, wy + 40, 208, 50, 'Disaggregated', 'prefill' if k == 0 else 'decode',
              'prefill' if k == 0 else 'decode')
        s.text(nx + 36, wy + 116, 'vLLM NIXL side channel :5600' if k == 0 else 'vLLM NIXL side channel :5600', 'mono')
        s.text(nx + 36, wy + 134, 'SGLang bootstrap :8998 (prefill)' if k == 0 else 'SGLang internal :30000', 'mono')
        s.box(nx + 20, 390, 464, 72, 'Local NVMe · /data', 'model weights (same pinned revision on both nodes) · compile caches', 'storage')
        # attachments
        s.line(nx + 150, 486, nx + 150, 540, '#475569', 1.8)
        s.line(nx + 354, 486, nx + 354, 598, ROSE, 2.4)
        s.text(nx + 162, 520, 'eth0', 'mono')
        s.text(nx + 366, 520, 'mlx5_4 … mlx5_11', 'mono')
    s.line(36, 540, 1324, 540, '#475569', 3)
    s.text(36, 560, 'CONTROL NETWORK', 'h', fill='#334155')
    s.text(170, 560, 'eth0 · private IPs', 'small')
    s.text(36, 576, 'HTTP :8000 · etcd :2379 · Dynamo TCP request plane · NIXL/SGLang handshakes · NCCL bootstrap', 'small')
    s.line(36, 598, 1324, 598, ROSE, 3)
    s.text(36, 618, 'DATA NETWORK', 'h', fill=ROSE)
    s.text(146, 618, '8 × 800 Gb/s InfiniBand rails', 'small', fill=ROSE)
    s.text(36, 634, 'KV cache (disaggregated only) · GPUDirect RDMA · UCX rc_x / rc', 'small')
    s.line(121, 320, 121, 540, '#475569', 1.8)
    s.render('reference-topology.svg')


# =============================================================================
# 11. Decision flow: topology first, then software
# =============================================================================
def decision_flow():
    s = SVG(1360, 800, 'Choosing a serving design',
            'Decide the topology from traffic, SLOs and fabric first; then pick the control plane and engine.',
            'Decision tree. If inputs are short and there is no strict tail-latency target, use aggregated replicas with '
            'KV-aware routing. Otherwise, if there is no RDMA or rack-scale NVLink, stay aggregated and fix the fabric. '
            'With the fabric, large MoE models use disaggregation with wide expert parallelism on rack-scale NVLink; '
            'other models use prefill/decode disaggregation over RDMA. Add KV tiers when prefix reuse exceeds GPU memory.')

    def diamond(cx, cy, w, h, lines):
        pts = f'{cx},{cy - h / 2} {cx + w / 2},{cy} {cx},{cy + h / 2} {cx - w / 2},{cy}'
        s.add(f'<polygon points="{pts}" fill="#FFFFFF" stroke="{LAYER["orch"][1]}" stroke-width="1.5"/>')
        for i, t in enumerate(lines):
            s.text(cx, cy - 6 + i * 16 - (len(lines) - 2) * 8, t, 'lbl', 'middle', size=12.5)

    cx = 330
    s.box(cx - 150, 96, 300, 48, 'Start from the workload', 'model · traffic shape · SLOs · hardware', 'access')
    s.arrow([(cx, 144), (cx, 166)], MUTED, 1.6)
    qs = [(236, ['Long inputs, or a strict', 'p99 ITL target?']),
          (386, ['GPUDirect RDMA or', 'rack-scale NVLink?']),
          (536, ['Large MoE that gains', 'from wide EP?'])]
    outs = [('Aggregated replicas', 'KV-aware routing · deploy 01', 'neutral', 'no'),
            ('Stay aggregated', 'fix the fabric before splitting', 'neutral', 'no'),
            ('P/D + wide-EP decode', 'rack-scale NVLink (NVL72)', 'decode', 'yes')]
    for (cy, lines), (t, sub, th, lab) in zip(qs, outs):
        diamond(cx, cy, 300, 116, lines)
        s.arrow([(cx + 150, cy), (596, cy)], MUTED, 1.6)
        s.text(cx + 168, cy - 8, lab, 'edge')
        s.box(600, cy - 30, 280, 60, t, sub, th)
    for cy, lab in ((236, 'yes'), (386, 'yes'), (536, 'no')):
        s.arrow([(cx, cy + 58), (cx, cy + 90)], MUTED, 1.6)
        s.text(cx + 10, cy + 80, lab, 'edge')
    s.box(cx - 150, 628, 300, 60, 'P/D disaggregation', 'over GPUDirect RDMA · deploy 02 / 03 / 04', 'prefill')
    # KV tiers band
    s.rect(36, 716, 844, 56, LAYER['storage'][0], LAYER['storage'][1], 12, 1.3)
    s.text(56, 740, 'For every outcome:', 'lbl', fill=LAYER['storage'][2], size=12.5)
    s.text(196, 740, 'if reusable prefixes exceed GPU memory, add KV tiers', 'sub', fill=INK)
    s.text(196, 758, 'host DRAM → local NVMe with GPUDirect Storage → shared storage  (chapter 08)', 'sub')

    # right: software choices
    rx, rw = 912, 412
    s.rect(rx, 96, rw, 676, '#FCFCFD', LINE, 14, 1.2)
    s.text(rx + 20, 124, 'THEN PICK THE SOFTWARE', 'h', fill=MUTED)
    s.text(rx + 20, 156, 'Serving control plane', 'lbl-lg', fill=LAYER['orch'][2])
    for i, (t, sub) in enumerate([('NVIDIA Dynamo', ['Docker or Kubernetes · all three engines', 'Planner (P/D autoscaling) · KVBM tiers']),
                                  ('llm-d', ['Kubernetes-native · Gateway API', 'pluggable endpoint picker · LMCache'])]):
        s.box(rx + 20, 172 + i * 86, rw - 40, 74, t, sub, 'orch')
    s.text(rx + 20, 376, 'Inference engine', 'lbl-lg', fill=LAYER['engine'][2])
    for i, (t, sub) in enumerate([('TensorRT-LLM', ['peak performance on NVIDIA GPUs', 'for supported models']),
                                  ('vLLM', ['broadest model and hardware coverage', 'primary engine for llm-d']),
                                  ('SGLang', ['prefix-heavy and agentic workloads', 'large-MoE P/D + wide-EP recipes'])]):
        s.box(rx + 20, 392 + i * 86, rw - 40, 74, t, sub, 'engine')
    s.text(rx + 20, 670, 'Validate every choice on your hardware:', 'sub', fill=INK)
    s.text(rx + 20, 688, 'same dataset, same SLOs, aggregated baseline first', 'sub')
    s.text(rx + 20, 718, 'benchmarks/ · deploy/', 'mono')
    s.render('decision-flow.svg')


if __name__ == '__main__':
    serving_stack()
    agg_vs_disagg()
    microservices()
    request_flow()
    kv_datapath()
    hardware_scaling()
    kv_hierarchy()
    orchestrators()
    model_architectures()
    reference_topology()
    decision_flow()
