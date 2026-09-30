# Benchmarks (code)

[Home](../README.md) › Benchmarks

Python package behind [06 · Benchmarking](../06-benchmarking/). Run modules from the repository root with `python -m benchmarks.<module>`.

| Module | Purpose |
|---|---|
| [generate_dataset.py](generate_dataset.py) | Expands the seed fixtures into deterministic, token-counted chatbot or agentic sessions |
| [run.py](run.py) | Streams sessions against an OpenAI-compatible endpoint and records TTFT, TPOT, ITL, throughput and failures per request |
| [metrics.py](metrics.py) | Metric definitions and summaries (unit-tested) |
| [collect.py](collect.py) | Rebuilds `results/summary.csv` from all run folders |
