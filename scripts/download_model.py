#!/usr/bin/env python3
"""Resolve and download one immutable checkpoint, checking capacity first."""
import argparse
import json
import shutil
from pathlib import Path

import yaml
from huggingface_hub import HfApi, snapshot_download

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', required=True)
    p.add_argument('--models', default=str(ROOT / 'configs/models.yaml'))
    p.add_argument('--revision', help='Use the same resolved SHA on the second node.')
    p.add_argument('--path')
    p.add_argument('--check-only', action='store_true')
    a = p.parse_args()
    m = yaml.safe_load(Path(a.models).read_text())[a.model]
    dest = Path(a.path or m['model_path'])
    info = HfApi().model_info(m['model_id'], revision=a.revision or m['revision'], files_metadata=True)
    sizes = {f.rfilename: f.size or 0 for f in info.siblings}
    total = sum(sizes.values())
    existing = sum(min((dest / name).stat().st_size, size) for name, size in sizes.items()
                   if (dest / name).is_file())
    parent = dest
    while not parent.exists():
        parent = parent.parent
    free = shutil.disk_usage(parent).free
    needed = max(total - existing, 0) + max(int(total * .05), 20 * 1024**3)
    record = {'model_id': m['model_id'], 'revision': info.sha, 'repository_bytes': total,
              'model_path': str(dest), 'free_bytes': free, 'required_free_bytes': needed}
    print(json.dumps(record, indent=2))
    marker = dest / 'DEPLOYMENT_MODEL.json'
    revision_marker = dest / 'DEPLOYED_REVISION'
    if revision_marker.exists() and revision_marker.read_text().strip() != info.sha:
        raise SystemExit('Existing DEPLOYED_REVISION differs. Use a new --path instead of mixing revisions.')
    if marker.exists():
        old = json.loads(marker.read_text())
        if (old['model_id'], old['revision']) != (m['model_id'], info.sha):
            raise SystemExit('Existing directory belongs to a different revision. Use a new --path; do not mix checkpoint files.')
    if free < needed:
        raise SystemExit('Insufficient disk capacity. Use a larger model volume on BOTH nodes.')
    if a.check_only:
        return
    dest.mkdir(parents=True, exist_ok=True)
    snapshot_download(repo_id=m['model_id'], revision=info.sha, local_dir=str(dest), max_workers=4)
    if not (dest / 'config.json').is_file():
        raise SystemExit('Missing config.json after download')
    marker.write_text(json.dumps(record, indent=2) + '\n')
    (dest / 'DEPLOYED_REVISION').write_text(info.sha + '\n')
    print('Pinned revision:', info.sha, '\nUse --revision with this SHA on the second node.')


if __name__ == '__main__':
    main()
