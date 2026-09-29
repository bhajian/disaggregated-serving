# Long-context throughput and latency measurements

Use a client on the same private network with enough CPU/RAM to tokenize and serialize multi-megabyte prompts. Start with concurrency 1; then increase to 2, 4 and 8 after checking memory and transfer stability. The runner holds one outstanding turn per session, preserving turn order while allowing concurrent sessions.

## Workloads and dataset contract

`datasets/seeds/chatbot.jsonl` and `agentic.jsonl` are small, original synthetic fixtures with no external download or private data. The generator expands them into deterministic indexed records with unique session prefixes. Chatbot sessions contain three turns. Agentic sessions contain three requests around recorded `read_file`/`run_tests` calls and tool results, preserving tool-call IDs and history.

This is **recorded workload replay**. Later turns use fixed recorded history, not the sampled answer from the previous request. It measures serving behavior under agent-like context growth and reuse, not agent success, tool-call accuracy, retrieval correctness or reasoning quality. No model-generated commands are executed. For production realism, supply your own redacted traces in the same format or use `--corpus` with a representative UTF-8 text corpus. Synthetic records cycle source text and are not a substitute for a production trace distribution.

One JSONL row is a session:

```json
{"id":"unique-session-id","workload":"agentic","turns":[{"messages":[{"role":"user","content":"Investigate this incident."}],"input_tokens":8}]}
```

Each turn may include `tools`. The generator writes complete snapshots, measured template-inclusive `input_tokens`, and a `.meta.json` file with seed, tokenizer, target and dataset hash. The runner accepts these files and equivalent user-provided snapshots. It never silently truncates a request.

## Prepare >250K input tokens

First render and restart the serving pair with `--max-model-len 262144 --max-num-seqs 4`. Do not send these datasets to the unchanged 32K deployment.

For Qwen, run on a machine with its local tokenizer files or use its pinned HF model/tokenizer revision:

```bash
python -m benchmarks.generate_dataset \
  --workload chatbot --sessions 8 --input-tokens 256000 \
  --output-tokens 512 --max-model-len 262144 \
  --tokenizer /data/models/qwen-480b \
  --out datasets/generated/qwen-chatbot-256k.jsonl

python -m benchmarks.generate_dataset \
  --workload agentic --sessions 8 --input-tokens 256000 \
  --output-tokens 512 --max-model-len 262144 \
  --tokenizer /data/models/qwen-480b \
  --out datasets/generated/qwen-agentic-256k.jsonl
```

Nemotron's tokenizer should be invoked with `--template-kwargs '{"enable_thinking":false,"force_nonempty_content":true}'` to match the served request defaults; use `--trust-remote-code` if its tokenizer requires the pinned repository code. Kimi must retain complete reasoning/tool history. For DeepSeek V4 or other custom tokenizers, generate against a **worker** that implements vLLM `/tokenize`:

```bash
python -m benchmarks.generate_dataset \
  --workload chatbot --sessions 8 --input-tokens 256000 \
  --output-tokens 512 --max-model-len 262144 \
  --tokenizer-url http://10.104.0.7:8200 \
  --template-kwargs '{"thinking":false}' \
  --out datasets/generated/deepseek-chatbot-256k.jsonl
```

That URL is for llm-d's decode engine and only performs tokenization. Dynamo's frontend need not expose `/tokenize`; prepare DeepSeek data with a temporary compatible vLLM tokenizer service or reuse data prepared in the llm-d phase. Inference benchmarks must still target the framework's frontend/router. If a reused dataset was counted with another tokenizer, its local count is only advisory; the runner checks server usage and requires the requested minimum.

The first turn targets approximately 256,000 tokens; every later turn is counted again with template and tool-schema overhead. Output reservation must fit for **every** turn. `--min-input-tokens 250001` verifies the requirement using actual server usage. To explore 512K or 1M-capable models, adjust both deployment and generation budgets and leave output/history headroom. Qwen's unextended profile stops at 262,144.

## Run one experiment

```bash
python -m benchmarks.run \
  --base-url http://10.104.0.51:8000/v1 \
  --model Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8 \
  --technology dynamo-compose \
  --deployment build/compose-qwen/deployment.json \
  --dataset datasets/generated/qwen-chatbot-256k.jsonl \
  --max-model-len 262144 --min-input-tokens 250001 --output-tokens 512 \
  --concurrency 1 --warmup 1 --timeout 3600 --cache-state uncontrolled \
  --metrics-url http://10.104.0.51:8081/metrics \
  --metrics-url http://10.104.0.7:8081/metrics
```

For Dynamo Kubernetes, change `--technology dynamo-k8s` and the deployment metadata path. For llm-d, use `--technology llmd-k8s`, the **router** URL, and worker metrics ports 8000/8200. The model ID and context must match `deployment.json`. Its model request defaults are merged into the request; `--extra-body` can override non-structural options. Authentication reads `BENCHMARK_API_KEY` from the environment and does not save it in run metadata.

Use `--token-ids` with vLLM where the endpoint supports `return_token_ids`. If unsupported, the request fails visibly; rerun without the flag and use chunk intervals plus TPOT. Do not claim exact ITL for that run. If the endpoint omits usage, the run is retained but marked invalid for token-based metrics; no character-based fallback is substituted.

The runner infers `backend` from `deployment.json`, or accepts `--backend vllm|sglang`. A conflicting backend or technology label is rejected. All result files retain the selected backend. See [backend comparisons](backends.md) for SGLang commands and ITL/tokenizer limitations.

## Sweep

```bash
CONCURRENCIES='1 2 4 8' REPETITIONS=3 bash scripts/sweep.sh \
  --base-url http://10.104.0.51:8000/v1 \
  --model Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8 \
  --technology dynamo-compose --deployment build/compose-qwen/deployment.json \
  --dataset datasets/generated/qwen-agentic-256k.jsonl \
  --max-model-len 262144 --min-input-tokens 250001 --output-tokens 512
```

Repeat for the chatbot file and for each technology/model after deployment. The sweep stops on errors/invalid measurements so they cannot disappear into a report. Individual failed runs retain their artifacts. Collect summaries with `python -m benchmarks.collect` after inspecting failures.

Closed-loop saturation is the default. `--session-rate 0.1` schedules 0.1 new sessions/sec with a concurrency cap, recording client queue time on each session's first turn. It is a paced session test, not an uncapped Poisson request generator. `--think-time 1` inserts one second between turns. Run duration/throughput include think time, client scheduling delays and failed-request time, but exclude warmup and metric snapshots.

## Metrics

| Column | Definition |
|---|---|
| `ttft_ms` | Request start to first generated payload (content, reasoning, tool-call payload or explicit token ID); role-only/empty deltas excluded |
| `first_content_ms` | Request start to first visible text content; may follow reasoning or be absent for a tool-only response |
| `e2e_ms` | Request start to stream completion/error |
| `tpot_ms` | `(last output arrival − first output arrival) / (completion_tokens − 1)`; absent for fewer than two tokens |
| `output_tps` | Per-request completion tokens / end-to-end seconds |
| `decode_tps` | `(completion_tokens − 1) / output-arrival span`; reciprocal of TPOT in seconds |
| `output_throughput_tps` | Valid successful output tokens / measured experiment wall time |
| `input_throughput_tps` | Valid successful input tokens / measured wall time; includes cached input, so this is not fresh GPU prefill work |
| `total_throughput_tps` | Valid input + output tokens / measured wall time |
| `itl_ms_*` | Client-observed token-arrival intervals **only when** every output event carries one explicit token ID and totals match server usage |
| `chunk_interval_ms_*` | Per-request intervals between generated streaming chunks, including multi-token chunks |
| `client_queue_ms` | Time waiting for the load generator's session concurrency slot; separate from request TTFT |

Distributions include mean, p50, p90, p95, p99 and max. Summary ITL/chunk percentiles pool intervals from valid successful requests; request latency percentiles pool requests. `itl_coverage` reports the fraction of valid requests that yielded token-resolved timings. TPOT is an arrival-span average, **not** evidence of individual token timing when chunks are batched. Client timings include network/proxy/parser buffering and do not isolate engine prefill, transfer or scheduler time. Reasoning tokens are included in server completion counts; hidden/batched reasoning can limit what client timing can resolve.

## Outputs and comparisons

Each run creates `results/<UTC timestamp>-<unique ID>/` with:

- `requests.csv`: one row per request, including errors, lengths, status and latency metrics.
- `requests.jsonl`: every output event, payload and arrival time for auditing; this can contain generated text from your prompts.
- `summary.csv` and `summary.json`: one experiment's rates/distributions and configuration identifiers.
- `metadata.json`: exact run arguments, dataset hash and deployment configuration; optional copied dataset manifest.
- `metrics-before-*.prom` / `metrics-after-*.prom`: optional worker snapshots, or explicit scrape errors.

`python -m benchmarks.collect` atomically rebuilds `results/summary.csv` from completed run summaries. There is no shared append file to corrupt when multiple runs finish together.

Open [notebooks/compare.ipynb](../notebooks/compare.ipynb) in your IDE or install JupyterLab and run `jupyter lab`. The notebook shows failure/validity counts before comparisons, groups repeated identical configurations, compares model/technology/backend columns, plots throughput and latency, and can export PNG/CSV charts. It starts empty until measured runs exist.

Use identical datasets, seeds, token/output budgets, sampling, reasoning modes, prefix-cache state, GPU allocation and client placement for technology comparisons. For cross-model tests, choose **same text** (different token counts) or **same token budget** (different generated files) and report which. The notebook retains dataset/config hashes so different workloads are not silently averaged together. Display actual input/output lengths, not just the configured cap: early stopping changes achieved throughput.

`--cache-state` is a label, not a cache-flush command. For a cold-session test, restart both workers before each repetition; later turns still intentionally reuse session prefixes. Warm tests deliberately replay the same dataset. Warmup uses disjoint short prompts to initialize the serving path without warming measured long prefixes. Prefix-cache hits reduce actual prefill work: retain metrics and distinguish warm/cold results. For serious tail latency comparisons, use more than the eight example sessions and at least three repetitions; a tiny sample's p99 is not a stable estimate.

Before recording a performance claim, establish actual P/D transfer and RDMA in logs/counters. Save GPU/driver inventory and resolved image IDs (`docker image inspect` or Kubernetes pod `imageID`) beside the run artifacts. Different engines and bundled engine versions make this a **stack comparison**; they do not isolate router overhead.
