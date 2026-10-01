"""Every relative link in the repository's Markdown resolves to a file or folder."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r'(?<!\!)\[[^\]]*\]\(([^)\s]+)\)|!\[[^\]]*\]\(([^)\s]+)\)')


def test_relative_links_resolve():
    files = subprocess.run(['git', 'ls-files', '-co', '--exclude-standard', '*.md'], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.split()
    broken = []
    for f in files:
        path = ROOT / f
        text = re.sub(r'```.*?```', '', path.read_text(), flags=re.S)   # ignore code blocks
        for m in LINK.finditer(text):
            target = (m.group(1) or m.group(2)).split('#')[0]
            if not target or re.match(r'[a-z]+:', target) or target.startswith('<'):
                continue
            if not (path.parent / target).resolve().exists():
                broken.append(f'{f}: {target}')
    assert not broken, '\n'.join(broken)
