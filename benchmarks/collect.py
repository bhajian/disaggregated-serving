#!/usr/bin/env python3
"""Rebuild the combined CSV atomically from immutable per-run summary files."""
import argparse
import csv
import os
from pathlib import Path
import tempfile


def collect(root):
    root = Path(root)
    rows = []
    for path in sorted(root.glob('*/summary.csv')):
        with path.open(newline='') as f:
            rows.extend(csv.DictReader(f))
    fields = sorted({k for r in rows for k in r})
    if not rows:
        print('No measured runs yet. Run benchmarks.run first.')
        return None
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', newline='', dir=root, delete=False) as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
        tmp = f.name
    dest = root / 'summary.csv'; os.replace(tmp, dest)
    print(f'{len(rows)} runs -> {dest}')
    return dest


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--results', default='results')
    collect(p.parse_args().results)
