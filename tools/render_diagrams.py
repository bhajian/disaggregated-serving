#!/usr/bin/env python3
"""Render architecture diagrams to PNG (2x) and editable draw.io files from one source.

    python tools/render_diagrams.py            # all diagrams
    python tools/render_diagrams.py serving-stack

Diagram specs live in assets/diagrams/src/diagrams.py as plain data: boxes, groups,
arrows and text placed on a pixel grid. This module draws them with matplotlib
(assets/diagrams/png/<name>.png, >= 2400 px wide) and writes the same geometry as
draw.io XML (assets/diagrams/src/<name>.drawio) so architects can edit either. Style:
white background, neutral greys, one accent (NVIDIA green #76B900), one typeface
(DejaVu Sans, bundled with matplotlib), no gradients or shadows.
"""
import html
import importlib.util
import sys
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'assets/diagrams/src'
PNG = ROOT / 'assets/diagrams/png'
SCALE = 2  # output pixels per spec pixel

PALETTE = {
    'ink': '#1A1A1A', 'muted': '#5F6368', 'line': '#3C4043', 'rule': '#C4C7CA',
    'fill': '#F3F4F5', 'fill2': '#E7E9EB', 'white': '#FFFFFF',
    'accent': '#76B900', 'accent_fill': '#EEF6E0', 'accent_ink': '#3F6300',
}
STYLES = {  # box style -> (fill, stroke, text, linestyle)
    'plain': ('white', 'line', 'ink', '-'), 'soft': ('fill', 'rule', 'ink', '-'), 'shade': ('fill2', 'rule', 'ink', '-'),
    'accent': ('accent_fill', 'accent', 'accent_ink', '-'), 'solid': ('accent', 'accent', 'white', '-'),
    'ghost': ('white', 'rule', 'muted', '--'), 'dark': ('line', 'line', 'white', '-'),
}
FONT = 'DejaVu Sans'


def load_specs():
    spec = importlib.util.spec_from_file_location('diagrams', SRC / 'diagrams.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.DIAGRAMS


# ----------------------------------------------------------------------------- PNG

def draw_png(d, path):
    W, H = d['size']
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100 * SCALE)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(H, 0); ax.axis('off')
    fig.patch.set_facecolor(PALETTE['white'])
    c = lambda k: PALETTE.get(k, k)

    def text(x, y, s, size=11, color='ink', weight='normal', ha='left', va='top', style='normal'):
        ax.text(x, y, s, fontsize=size * 0.75, color=c(color), fontfamily=FONT, fontweight=weight,
                ha=ha, va=va, linespacing=1.35, fontstyle=style)

    if d.get('title'):
        text(40, 28, d['title'], 20, weight='bold')
    if d.get('subtitle'):
        text(40, 60, d['subtitle'], 12, 'muted')
    for g in d.get('groups', []):
        fill, stroke, ink, ls = STYLES[g.get('style', 'ghost')]
        ax.add_patch(FancyBboxPatch((g['x'], g['y']), g['w'], g['h'], boxstyle='round,pad=0,rounding_size=10',
                                    fc=c(fill), ec=c(stroke), lw=1.2, ls=ls))
        text(g['x'] + 16, g['y'] + 12, g['label'], 11, ink if ink != 'ink' else 'muted', weight='bold')
        if g.get('badge'):
            text(g['x'] + g['w'] - 16, g['y'] + 12, g['badge'], 10, g.get('badge_color', 'muted'), weight='bold', ha='right')
    for b in d.get('boxes', []):
        fill, stroke, ink, ls = STYLES[b.get('style', 'plain')]
        ax.add_patch(FancyBboxPatch((b['x'], b['y']), b['w'], b['h'], boxstyle='round,pad=0,rounding_size=6',
                                    fc=c(fill), ec=c(stroke), lw=1.4 if b.get('style') != 'ghost' else 1.0, ls=ls))
        cx = b['x'] + b['w'] / 2
        weight = b.get('weight', 'bold')
        if b.get('sub'):
            text(cx, b['y'] + 12, b['label'], b.get('size', 12), ink, weight, 'center')
            text(cx, b['y'] + 12 + 20 * (b['label'].count('\n') + 1), b['sub'], b.get('subsize', 10),
                 'muted' if ink == 'ink' else ink, ha='center')
        else:
            text(cx, b['y'] + b['h'] / 2, b['label'], b.get('size', 12), ink, weight, 'center', 'center')
    for a in d.get('arrows', []):
        color = c({'accent': 'accent', 'muted': 'rule'}.get(a.get('style'), 'line'))
        pts = a['points']
        for i in range(len(pts) - 1):
            last = i == len(pts) - 2
            ax.add_patch(FancyArrowPatch(pts[i], pts[i + 1], arrowstyle='-|>' if last else '-', mutation_scale=12,
                                         color=color, lw=2.2 if a.get('style') == 'accent' else 1.5,
                                         ls='--' if a.get('dashed') else '-', shrinkA=0, shrinkB=0))
            if a.get('both') and i == 0:
                ax.add_patch(FancyArrowPatch(pts[1], pts[0], arrowstyle='-|>', mutation_scale=12, color=color,
                                             lw=1.5, shrinkA=0, shrinkB=0))
        if a.get('label'):
            lx, ly = a.get('label_at', ((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2))
            text(lx, ly, a['label'], 10, 'accent_ink' if a.get('style') == 'accent' else 'muted',
                 ha=a.get('label_ha', 'center'), va='center')
    for t in d.get('texts', []):
        text(t['x'], t['y'], t['text'], t.get('size', 11), t.get('color', 'ink'), t.get('weight', 'normal'),
             t.get('ha', 'left'), t.get('va', 'top'), t.get('style', 'normal'))
    for p in d.get('points', []):
        ax.plot([p['x']], [p['y']], marker='o', ms=7 if p.get('style') != 'accent' else 9,
                color=c('accent' if p.get('style') == 'accent' else 'line'), zorder=5)
        text(p['x'] + 12, p['y'], p['label'], 10, 'ink', va='center')
    fig.savefig(path, dpi=100 * SCALE, facecolor=PALETTE['white'])
    plt.close(fig)


# ----------------------------------------------------------------------------- draw.io

def drawio(d):
    W, H = d['size']
    cells, n = [], [1]

    def cid():
        n[0] += 1
        return f'c{n[0]}'

    def esc(s):
        return html.escape(s).replace('\n', '&#xa;')

    def box(x, y, w, h, value, style):
        cells.append(f'<mxCell id="{cid()}" value="{esc(value)}" style="{style}" vertex="1" parent="1">'
                     f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')

    def color(k):
        return PALETTE.get(k, k)

    base = f'html=1;fontFamily={FONT};whiteSpace=wrap;'
    if d.get('title'):
        box(40, 20, W - 80, 30, d['title'], base + 'text;fontSize=20;fontStyle=1;align=left;verticalAlign=top;')
    if d.get('subtitle'):
        box(40, 54, W - 80, 24, d['subtitle'], base + f'text;fontSize=12;fontColor={color("muted")};align=left;')
    for g in d.get('groups', []):
        fill, stroke, ink, ls = STYLES[g.get('style', 'ghost')]
        label = g['label'] + (f'    [{g["badge"]}]' if g.get('badge') else '')
        box(g['x'], g['y'], g['w'], g['h'], label, base + f'rounded=1;arcSize=4;fillColor={color(fill)};strokeColor={color(stroke)};'
            f'dashed={int(ls == "--")};verticalAlign=top;align=left;spacingLeft=14;fontStyle=1;fontColor={color("muted")};')
    for b in d.get('boxes', []):
        fill, stroke, ink, ls = STYLES[b.get('style', 'plain')]
        value = b['label'] + (f'\n{b["sub"]}' if b.get('sub') else '')
        box(b['x'], b['y'], b['w'], b['h'], value, base + f'rounded=1;arcSize=6;fillColor={color(fill)};strokeColor={color(stroke)};'
            f'fontColor={color(ink)};dashed={int(ls == "--")};fontSize={b.get("size", 12)};'
            + ('fontStyle=1;' if b.get('weight', 'bold') == 'bold' else ''))
    for a in d.get('arrows', []):
        pts = a['points']
        stroke = color({'accent': 'accent', 'muted': 'rule'}.get(a.get('style'), 'line'))
        style = (base + f'endArrow=block;endFill=1;strokeColor={stroke};strokeWidth={2 if a.get("style") == "accent" else 1.5};'
                 f'dashed={int(bool(a.get("dashed")))};fontColor={color("muted")};fontSize=10;'
                 + ('startArrow=block;startFill=1;' if a.get('both') else ''))
        mid = ''.join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in pts[1:-1])
        cells.append(f'<mxCell id="{cid()}" value="{esc(a.get("label", ""))}" style="{style}" edge="1" parent="1">'
                     f'<mxGeometry relative="1" as="geometry"><mxPoint x="{pts[0][0]}" y="{pts[0][1]}" as="sourcePoint"/>'
                     f'<mxPoint x="{pts[-1][0]}" y="{pts[-1][1]}" as="targetPoint"/>'
                     + (f'<Array as="points">{mid}</Array>' if mid else '') + '</mxGeometry></mxCell>')
    for t in d.get('texts', []):
        box(t['x'] - (300 if t.get('ha') == 'center' else 0), t['y'], 600 if t.get('ha') == 'center' else 520, 24, t['text'],
            base + f'text;fontSize={t.get("size", 11)};fontColor={color(t.get("color", "ink"))};'
            f'align={ {"left": "left", "center": "center", "right": "right"}[t.get("ha", "left")] };verticalAlign=top;'
            + ('fontStyle=1;' if t.get('weight') == 'bold' else ''))
    for p in d.get('points', []):
        box(p['x'] - 5, p['y'] - 5, 10, 10, '', f'ellipse;fillColor={color("accent" if p.get("style") == "accent" else "line")};strokeColor=none;')
        box(p['x'] + 12, p['y'] - 10, 360, 20, p['label'], base + 'text;fontSize=10;align=left;')
    body = ''.join(cells)
    return (f'<mxfile host="tools/render_diagrams.py"><diagram name="{esc(d["title"] or "")}">'
            f'<mxGraphModel dx="{W}" dy="{H}" grid="1" gridSize="10" page="1" pageWidth="{W}" pageHeight="{H}" background="#FFFFFF">'
            f'<root><mxCell id="0"/><mxCell id="1" parent="0"/>{body}</root></mxGraphModel></diagram></mxfile>\n')


def main(names=None):
    PNG.mkdir(parents=True, exist_ok=True)
    specs = load_specs()
    for name, d in specs.items():
        if names and name not in names:
            continue
        draw_png(d, PNG / f'{name}.png')
        (SRC / f'{name}.drawio').write_text(drawio(d))
        print('rendered', name)


if __name__ == '__main__':
    main(sys.argv[1:])
