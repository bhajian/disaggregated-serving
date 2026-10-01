# Lab overlay

[Home](../../../README.md) › [Deploy](../../README.md) › [Overlays](../README.md) › Lab

> The lab path keeps the hand-written Deployments that produced the recorded results:
> `hostNetwork`, `IPC_LOCK`/`SYS_RESOURCE`, a single etcd and manual topology switching.
> Use it to reproduce a measurement, not to run production.

Lab variants live with their site because they are tied to that site's measured
configuration:

| Site / model | Variants |
| --- | --- |
| [nebius-h200-2x8 / nemotron-3-nano](../../sites/nebius-h200-2x8/nemotron-3-nano/lab/) | tp8-aggregated, tp8-disaggregated, tp4-aggregated, tp4-disaggregated, model-download, benchmark clients |
| [nebius-h200-2x8 / deepseek-v4-pro](../../sites/nebius-h200-2x8/deepseek-v4-pro/lab/) | aggregated, disaggregated, model-download |
