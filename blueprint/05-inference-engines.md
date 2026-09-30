# 05 · Inference engines: TensorRT-LLM, vLLM, SGLang

[Home](../README.md) › [Blueprint](README.md) › 05 · Inference engines

The engine is the process runtime of the serving OS. It owns the GPUs of one worker and turns a stream of requests into batched kernel launches.

## What every modern engine does

| Capability | What it solves |
|---|---|
| **Continuous (in-flight) batching** | Add and retire sequences every step instead of waiting for a whole batch |
| **Paged KV cache** | Allocate KV in fixed-size blocks, like memory pages, so memory is not fragmented and blocks can be shared |
| **Prefix caching** | Keep KV blocks of finished requests, so a repeated prefix skips prefill |
| **Chunked prefill** | Split long prompts into chunks that interleave with decode steps |
| **Speculative decoding** | Draft several tokens cheaply (MTP heads, EAGLE, n-gram) and verify them in one pass |
| **Quantization** | FP8 and FP4 (NVFP4 on Blackwell) weights and KV cache for memory and bandwidth |
| **Parallelism** | Tensor, pipeline, expert, data-parallel attention, context parallelism ([chapter 09](09-parallelism-and-sizing.md)) |
| **Disaggregation hooks** | Prefill-only and decode-only modes with a KV transfer connector |
| **KV events** | Publish block stored/removed events so a router can track cache locality |

## The three engines

### TensorRT-LLM
NVIDIA's inference library, with a PyTorch-based runtime and highly optimized kernels for NVIDIA GPUs (FP8, NVFP4, attention and MoE kernels). It supports disaggregated serving through a **KV cache transceiver** with UCX or NIXL backends, plus wide expert parallelism.
**Choose it when** you run NVIDIA GPUs, your model is supported, and the last increment of throughput and latency matters. Dynamo integrates it as `dynamo.trtllm`.

### vLLM
The most widely deployed open engine. It introduced PagedAttention, and supports the broadest range of models and accelerators. Disaggregation works through **KV connectors**, notably the `NixlConnector` used in this repository, with LMCache and other connectors available.
**Choose it when** you need broad model coverage, fast support for new models, or portability across hardware. It is the primary engine for llm-d and fully supported by Dynamo.

### SGLang
An engine built around **RadixAttention** (a radix-tree prefix cache) and an efficient scheduler, strong on agentic, structured-output and multi-turn workloads. It has well-known large-scale deployments of DeepSeek-class MoE with prefill/decode disaggregation and wide EP. Disaggregation uses a bootstrap handshake with **NIXL** or **Mooncake** transfer backends.
**Choose it when** workloads are prefix-heavy or agentic, or when you follow SGLang's large-MoE recipes. Dynamo integrates it as `dynamo.sglang`, and llm-d has an SGLang guide.

## Comparison

| | TensorRT-LLM | vLLM | SGLang |
|---|---|---|---|
| KV management | Paged KV, KV reuse | PagedAttention, hash-based prefix cache | RadixAttention (radix-tree prefix cache) |
| P/D transfer | Cache transceiver: UCX, NIXL | `NixlConnector`; LMCache and others | NIXL, Mooncake |
| Parallelism | TP, PP, EP (wide EP), attention DP | TP, PP, EP, DP attention | TP, EP (wide EP), DP attention, PP |
| Low precision | FP8, NVFP4 (strongest NVIDIA kernel coverage) | FP8, NVFP4, INT4/INT8 schemes | FP8, NVFP4, INT schemes |
| Speculative decoding | MTP, EAGLE, draft models | EAGLE, MTP, n-gram, draft models | EAGLE, MTP, n-gram |
| Hardware | NVIDIA | NVIDIA plus other accelerators | NVIDIA plus other accelerators |
| Dynamo | ✓ | ✓ | ✓ |
| llm-d | not a documented path | ✓ primary | ✓ guide |
| In this repository | [roadmap](../ROADMAP.md) | tracks 01, 02, 04 | tracks 01, 03, 04 |

Capabilities change release to release. Treat this table as orientation, and check the release notes of the version you pin.

## Rules that keep engines interchangeable

1. **Use each engine's complete image.** Never install one engine into another's container. Model-specific images (for example, NVIDIA's patched previews for new models) exist for a reason.
2. **Map, don't copy, flags.** The same concept has different names and different scheduler semantics: `--max-model-len` vs `--context-length`, `--gpu-memory-utilization` vs `--mem-fraction-static`. See [reference/vllm-vs-sglang.md](../reference/vllm-vs-sglang.md).
3. **Record precision.** KV dtype defaults differ (this repository uses FP8 KV for vLLM and `auto` for SGLang). Equal throughput at different precision is not an engine comparison.
4. **Parsers are engine- and model-specific.** Tool-call and reasoning parsers differ by engine and by model. Validate structured output after every change.
5. **Compare stacks, not engines.** Different images bundle different CUDA, NCCL and NIXL versions. Report results as a stack comparison ([benchmarks/](../benchmarks/)).

---

**Next:** [06 · Model architectures](06-model-architectures.md)
