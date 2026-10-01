"""Diagrams are generated from one source, large enough, and every embedded image exists."""
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def specs():
    import importlib.util
    spec = importlib.util.spec_from_file_location('d', ROOT / 'assets/diagrams/src/diagrams.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod.DIAGRAMS


@pytest.mark.parametrize('name', sorted(specs()))
def test_png_and_drawio_exist_and_are_current(name):
    from tools.render_diagrams import drawio
    png = ROOT / f'assets/diagrams/png/{name}.png'
    with png.open('rb') as f:
        head = f.read(24)
    width = int.from_bytes(head[16:20], 'big')
    assert head[:8] == b'\x89PNG\r\n\x1a\n' and width >= 2400, (name, width)
    src = ROOT / f'assets/diagrams/src/{name}.drawio'
    ET.fromstring(src.read_text())
    assert src.read_text() == drawio(specs()[name]), f'{name}.drawio is stale; run tools/render_diagrams.py'


def test_every_embedded_image_exists_and_no_svg_remains():
    files = subprocess.run(['git', 'ls-files', '-co', '--exclude-standard', '*.md'], cwd=ROOT,
                           capture_output=True, text=True).stdout.split()
    missing = []
    for f in files:
        for target in re.findall(r'!\[[^\]]*\]\(([^)]+\.(?:png|svg))\)', (ROOT / f).read_text()):
            if not (ROOT / f).parent.joinpath(target).resolve().exists():
                missing.append(f'{f}: {target}')
    assert not missing, missing
    assert not list((ROOT / 'assets/diagrams').glob('*.svg'))
