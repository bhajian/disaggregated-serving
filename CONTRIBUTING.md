# Contributing

[Home](README.md) › Contributing

This repository is a reference architecture: readers must be able to understand **exactly** what runs. Contributions keep that property.

## Principles

- **Readable over automated.** Deployment files are hand-written and commented. Generators such as `tools/render.py` may help you draft, but the committed file is what readers study.
- **Every folder has a README.** A test enforces it.
- **Claims are sourced or measured.** Product capabilities cite pinned versions in [reference/sources.md](reference/sources.md). Performance claims come from [benchmarks/](benchmarks/) runs with their run records. Nothing is fabricated.
- **Unvalidated is labeled.** Anything not run on hardware says so.

## Adding a deployment track

1. Create `deploy/NN-<control-plane>-<topology>-<engine>/` with `README.md`, `docker/` and `kubernetes/`, following an existing track.
2. **Docker:** `node-a.yaml` and `node-b.yaml`. Site values come only from `deploy/cluster.env`. Write engine flags out in full, with a comment above the `exec` line explaining each flag group.
3. **Kubernetes:** numbered manifests (`00-namespace`, `01-site-config`, `10-…`, `20-…`, `30-…`), a `kustomization.yaml` listing them in order, node placement by `llm-serving/node` labels, pod IPs from the Downward API, and a dedicated namespace.
4. **Run record:** a `deployment.json` in both `docker/` and `kubernetes/` with `technology`, `backend`, `topology`, `image`, `max_model_len` and `model` (id, revision, request defaults). Add new technology labels to `benchmarks/run.py`.
5. **Guides:** each platform README covers what you deploy, files, before you start, step-by-step deploy, verify, proof of KV transfer (if disaggregated), see results, clean up and troubleshooting.
6. **Tests:** add the track to `tests/test_reference_manifests.py` so Compose and Kubernetes stay identical and match the model catalog.
7. **Index:** add the track to the matrix in [deploy/README.md](deploy/README.md) and the root README, and update [ROADMAP.md](ROADMAP.md).

## Editing diagrams

Diagrams are PNG files (with editable draw.io sources) generated from [assets/diagrams/src/diagrams.py](assets/diagrams/src/diagrams.py) by [tools/render_diagrams.py](tools/render_diagrams.py). Edit the spec, never the PNG.

## Checks before a pull request

```bash
python -m pytest -q                 # offline: manifests, generator, metrics, notebook
python tools/validate.py            # upstream Kubernetes / Compose / InferencePool schemas
python tools/render_diagrams.py && git diff --stat assets/diagrams
```

## Writing style

Lead with the outcome. One idea per sentence. Tables for comparisons, numbered lists for steps. Name files and flags only where the reader must act on them.
