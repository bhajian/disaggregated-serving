# Configs

[Home](../README.md) › Configs

Inputs for the optional [tools](../tools/). The hand-written deployments in deploy/01–03 do not read these files.

| File | Contents |
|---|---|
| [models.yaml](models.yaml) | Model catalog: HF id, pinned revision, local path, context limit, and vLLM and SGLang engine flags, parsers and environment per model. The authoritative source when [switching models](../reference/models.md#switching-a-reference-deployment-to-another-model). |
| [cluster.yaml](cluster.yaml) | Node names, IPs, InfiniBand devices and images, used by `tools/render.py` and the llm-d manifests. The Docker reference deployments use [deploy/legacy-compose/cluster.env.example](../deploy/legacy-compose/cluster.env.example) instead. |
