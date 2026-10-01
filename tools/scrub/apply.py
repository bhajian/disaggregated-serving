"""Apply a git filter-repo --replace-text map to tracked text files.

    python tools/scrub/apply.py PATH/TO/replacements.txt

The map lists the values being removed, so it is kept outside the repository.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES = []
for line in Path(sys.argv[1]).read_text().splitlines():
    if not line.strip() or line.startswith('#'):
        continue
    old, new = line.split('==>')
    RULES.append((re.compile(old[6:]) if old.startswith('regex:') else re.compile(re.escape(old)), new))
SELF = {'tools/scrub/apply.py'}
changed = 0
for name in subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True).stdout.split('\n'):
    if not name or name in SELF:
        continue
    path = ROOT / name
    data = path.read_bytes()
    if b'\0' in data[:8192]:
        continue
    text = data.decode('utf-8', errors='surrogateescape')
    new = text
    for pattern, repl in RULES:
        new = pattern.sub(lambda m: repl, new)
    if new != text:
        path.write_bytes(new.encode('utf-8', errors='surrogateescape')); changed += 1
print(changed, 'files changed')
