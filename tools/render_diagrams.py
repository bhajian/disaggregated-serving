#!/usr/bin/env python3
"""Render architecture diagrams to PNG (2x) and editable draw.io files from one source.

    python tools/render_diagrams.py            # all diagrams
    python tools/render_diagrams.py serving-stack

Diagram specs live in assets/diagrams/src/diagrams.py as plain data: boxes, groups,
arrows and text placed on a pixel grid. This module draws them with matplotlib
(assets/diagrams/png/<name>.png, >= 2400 px wide) and writes the same geometry as
draw.io XML (assets/diagrams/src/<name>.drawio) so architects can edit either. Style:
white background, neutral greys, one accent (NVIDIA green #76B900), one typeface
(Inter, bundled in assets/diagrams/fonts), no gradients or shadows.

Rendering fails if any text overflows its box, its group or the canvas, or collides
with a box it does not belong to, so a layout edit cannot silently clip a label.
"""
import html
import importlib.util
import sys
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
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
FONT = 'Inter'
FONT_SCALE = 1.4  # spec sizes were set for 1400 px canvases read at full width; READMEs show them at ~60%
LINE = 1.3  # line spacing
for _ttf in sorted((ROOT / 'assets/diagrams/fonts').glob('*.ttf')):
    font_manager.fontManager.addfont(str(_ttf))
WEIGHT = {'bold': 'semibold', 'normal': 'normal'}


def load_specs():
    spec = importlib.util.spec_from_file_location('diagrams', SRC / 'diagrams.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.DIAGRAMS


# ----------------------------------------------------------------------------- PNG

def draw_png(d, path):
    """Draw one diagram; return a list of layout problems (overflow and collisions)."""
    W, H = d['size']
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100 * SCALE)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(H, 0); ax.axis('off')
    fig.patch.set_facecolor(PALETTE['white'])
    c = lambda k: PALETTE.get(k, k)
    placed = []  # (artist, container rect or None, label for errors)
    boxes = []

    def text(x, y, s, size=11, color='ink', weight='normal', ha='left', va='top', style='normal', inside=None):
        t = ax.text(x, y, s, fontsize=size * FONT_SCALE * 0.72, color=c(color), fontfamily=FONT,
                    fontweight=WEIGHT.get(weight, weight), ha=ha, va=va, linespacing=LINE, fontstyle=style)
        placed.append((t, inside, s.split('\n')[0][:50]))
        return t

    def lines(s):
        return s.count('\n') + 1

    if d.get('title'):
        text(40, 26, d['title'], 20, weight='bold')
    if d.get('subtitle'):
        text(40, 66, d['subtitle'], 12, 'muted')
    for g in d.get('groups', []):
        fill, stroke, ink, ls = STYLES[g.get('style', 'ghost')]
        ax.add_patch(FancyBboxPatch((g['x'], g['y']), g['w'], g['h'], boxstyle='round,pad=0,rounding_size=10',
                                    fc=c(fill), ec=c(stroke), lw=1.2, ls=ls))
        rect = (g['x'], g['y'], g['w'], g['h'])
        text(g['x'] + 16, g['y'] + 12, g['label'], 11, ink if ink != 'ink' else 'muted', weight='bold', inside=rect)
        if g.get('badge'):
            text(g['x'] + g['w'] - 16, g['y'] + 12, g['badge'], 10, g.get('badge_color', 'muted'), weight='bold', ha='right', inside=rect)
    rects = [(b['x'], b['y'], b['w'], b['h']) for b in d.get('boxes', [])]
    for b, rect in zip(d.get('boxes', []), rects):
        fill, stroke, ink, ls = STYLES[b.get('style', 'plain')]
        ax.add_patch(FancyBboxPatch((b['x'], b['y']), b['w'], b['h'], boxstyle='round,pad=0,rounding_size=6',
                                    fc=c(fill), ec=c(stroke), lw=1.4 if b.get('style') != 'ghost' else 1.0, ls=ls))
        boxes.append(rect)
        nested = b.get('align') == 'top' or any(o != rect and _contains(rect, o) for o in rects)  # region boxes keep text at the top
        cx, cy = b['x'] + b['w'] / 2, b['y'] + b['h'] / 2
        weight = b.get('weight', 'bold')
        size = b.get('size', 12)
        if b.get('sub'):
            subsize = b.get('subsize', 10.5)
            lh, slh, gap = size * FONT_SCALE * LINE, subsize * FONT_SCALE * LINE, 4
            top = b['y'] + 12 if nested else cy - (lh * lines(b['label']) + gap + slh * lines(b['sub'])) / 2
            text(cx, top, b['label'], size, ink, weight, 'center', inside=rect)
            text(cx, top + lh * lines(b['label']) + gap, b['sub'], subsize, 'muted' if ink == 'ink' else ink, ha='center', inside=rect)
        else:
            text(cx, cy, b['label'], size, ink, weight, 'center', 'center' if '\n' in b['label'] else 'center_baseline', inside=rect)
    for a in d.get('arrows', []):
        color = c({'accent': 'accent', 'muted': 'rule'}.get(a.get('style'), 'line'))
        pts = a['points']
        for i in range(len(pts) - 1):
            last = i == len(pts) - 2
            ax.add_patch(FancyArrowPatch(pts[i], pts[i + 1], arrowstyle='-|>' if last else '-', mutation_scale=14,
                                         color=color, lw=2.4 if a.get('style') == 'accent' else 1.6,
                                         ls='--' if a.get('dashed') else '-', shrinkA=0, shrinkB=0))
            if a.get('both') and i == 0:
                ax.add_patch(FancyArrowPatch(pts[1], pts[0], arrowstyle='-|>', mutation_scale=14, color=color,
                                             lw=1.6, shrinkA=0, shrinkB=0))
        if a.get('label'):
            lx, ly = a.get('label_at', ((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2))
            t = text(lx, ly, a['label'], 10.5, 'accent_ink' if a.get('style') == 'accent' else 'muted',
                     ha=a.get('label_ha', 'center'), va='center')
            t.set_bbox(dict(fc=PALETTE['white'], ec='none', pad=1.5))
    for t in d.get('texts', []):
        text(t['x'], t['y'], t['text'], t.get('size', 11), t.get('color', 'ink'), t.get('weight', 'normal'),
             t.get('ha', 'left'), t.get('va', 'top'), t.get('style', 'normal'))
    for p in d.get('points', []):
        ax.plot([p['x']], [p['y']], marker='o', ms=8 if p.get('style') != 'accent' else 10,
                color=c('accent' if p.get('style') == 'accent' else 'line'), zorder=5)
        text(p['x'] + 14, p['y'], p['label'], 10.5, 'ink', va='center')
    problems = check(fig, ax, placed, boxes, W, H)
    fig.savefig(path, dpi=100 * SCALE, facecolor=PALETTE['white'])
    plt.close(fig)
    return problems


def check(fig, ax, placed, boxes, W, H, pad=6):
    """Text must sit inside its own box (with padding), on the canvas, and off every other box.

    Free text may annotate a region by sitting wholly inside a box; crossing a box edge is a collision.
    No two texts may overlap."""
    r = fig.canvas.get_renderer()
    inv = ax.transData.inverted()
    out = []
    seen = []
    for t, inside, name in placed:
        (x0, y1), (x1, y0) = inv.transform(t.get_window_extent(r).get_points())  # y axis is flipped
        for sx0, sy0, sx1, sy1, sname in seen:  # extents include line padding; allow 3 px of it to touch
            if x0 + 3 < sx1 - 3 and x1 - 3 > sx0 + 3 and y0 + 3 < sy1 - 3 and y1 - 3 > sy0 + 3:
                out.append(f'overlaps text {sname!r}: {name!r}')
        seen.append((x0, y0, x1, y1, name))
        if x0 < 8 or y0 < 8 or x1 > W - 8 or y1 > H - 8:
            out.append(f'off canvas: {name!r}')
        if inside:
            bx, by, bw, bh = inside
            if x0 < bx + pad or x1 > bx + bw - pad or y0 < by + 3 or y1 > by + bh - 3:
                out.append(f'overflows its box by {max(bx + pad - x0, x1 - bx - bw + pad, by + 3 - y0, y1 - by - bh + 3):.0f}px: {name!r}')
        for bx, by, bw, bh in boxes:
            if inside == (bx, by, bw, bh) or (inside and _contains((bx, by, bw, bh), inside)):
                continue
            if inside is None and _contains((bx, by, bw, bh), (x0, y0, x1 - x0, y1 - y0)):
                continue
            if x0 < bx + bw and x1 > bx and y0 < by + bh and y1 > by:
                out.append(f'collides with box at ({bx:.0f},{by:.0f}): {name!r}')
    return out


def _contains(outer, inner):
    return outer[0] <= inner[0] and outer[1] <= inner[1] and outer[0] + outer[2] >= inner[0] + inner[2] and outer[1] + outer[3] >= inner[1] + inner[3]


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
    fs = lambda size: round(size * FONT_SCALE, 1)
    if d.get('title'):
        box(40, 20, W - 80, 30, d['title'], base + f'text;fontSize={fs(20)};fontStyle=1;align=left;verticalAlign=top;')
    if d.get('subtitle'):
        box(40, 54, W - 80, 24, d['subtitle'], base + f'text;fontSize={fs(12)};fontColor={color("muted")};align=left;')
    for g in d.get('groups', []):
        fill, stroke, ink, ls = STYLES[g.get('style', 'ghost')]
        label = g['label'] + (f'    [{g["badge"]}]' if g.get('badge') else '')
        box(g['x'], g['y'], g['w'], g['h'], label, base + f'rounded=1;arcSize=4;fillColor={color(fill)};strokeColor={color(stroke)};'
            f'dashed={int(ls == "--")};verticalAlign=top;align=left;spacingLeft=14;fontStyle=1;fontSize={fs(11)};fontColor={color("muted")};')
    for b in d.get('boxes', []):
        fill, stroke, ink, ls = STYLES[b.get('style', 'plain')]
        value = b['label'] + (f'\n{b["sub"]}' if b.get('sub') else '')
        box(b['x'], b['y'], b['w'], b['h'], value, base + f'rounded=1;arcSize=6;fillColor={color(fill)};strokeColor={color(stroke)};'
            f'fontColor={color(ink)};dashed={int(ls == "--")};fontSize={fs(b.get("size", 12))};'
            + ('fontStyle=1;' if b.get('weight', 'bold') == 'bold' else ''))
    for a in d.get('arrows', []):
        pts = a['points']
        stroke = color({'accent': 'accent', 'muted': 'rule'}.get(a.get('style'), 'line'))
        style = (base + f'endArrow=block;endFill=1;strokeColor={stroke};strokeWidth={2 if a.get("style") == "accent" else 1.5};'
                 f'dashed={int(bool(a.get("dashed")))};fontColor={color("muted")};fontSize={fs(10.5)};'
                 + ('startArrow=block;startFill=1;' if a.get('both') else ''))
        mid = ''.join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in pts[1:-1])
        cells.append(f'<mxCell id="{cid()}" value="{esc(a.get("label", ""))}" style="{style}" edge="1" parent="1">'
                     f'<mxGeometry relative="1" as="geometry"><mxPoint x="{pts[0][0]}" y="{pts[0][1]}" as="sourcePoint"/>'
                     f'<mxPoint x="{pts[-1][0]}" y="{pts[-1][1]}" as="targetPoint"/>'
                     + (f'<Array as="points">{mid}</Array>' if mid else '') + '</mxGeometry></mxCell>')
    for t in d.get('texts', []):
        box(t['x'] - (300 if t.get('ha') == 'center' else 0), t['y'], 600 if t.get('ha') == 'center' else 520, 24, t['text'],
            base + f'text;fontSize={fs(t.get("size", 11))};fontColor={color(t.get("color", "ink"))};'
            f'align={ {"left": "left", "center": "center", "right": "right"}[t.get("ha", "left")] };verticalAlign=top;'
            + ('fontStyle=1;' if t.get('weight') == 'bold' else ''))
    for p in d.get('points', []):
        box(p['x'] - 5, p['y'] - 5, 10, 10, '', f'ellipse;fillColor={color("accent" if p.get("style") == "accent" else "line")};strokeColor=none;')
        box(p['x'] + 12, p['y'] - 10, 360, 20, p['label'], base + f'text;fontSize={fs(10.5)};align=left;')
    body = ''.join(cells)
    return (f'<mxfile host="tools/render_diagrams.py"><diagram name="{esc(d["title"] or "")}">'
            f'<mxGraphModel dx="{W}" dy="{H}" grid="1" gridSize="10" page="1" pageWidth="{W}" pageHeight="{H}" background="#FFFFFF">'
            f'<root><mxCell id="0"/><mxCell id="1" parent="0"/>{body}</root></mxGraphModel></diagram></mxfile>\n')


def main(names=None):
    PNG.mkdir(parents=True, exist_ok=True)
    specs = load_specs()
    failed = []
    for name, d in specs.items():
        if names and name not in names:
            continue
        problems = draw_png(d, PNG / f'{name}.png')
        (SRC / f'{name}.drawio').write_text(drawio(d))
        print('rendered', name)
        failed += [f'{name}: {p}' for p in problems]
    if failed:
        sys.exit('layout problems:\n  ' + '\n  '.join(failed))


if __name__ == '__main__':
    main(sys.argv[1:])
