# Notebooks

[Home](../README.md) › Notebooks

[compare.ipynb](compare.ipynb) reads `results/*/summary.csv`. It shows failures and validity first, then compares model × technology × backend cohorts with tables and charts (TTFT, TPOT, ITL, throughput), and can export PNG and CSV files to `results/analysis/`. It runs with no results (empty report). Set `DISAGG_RESULTS` to read another folder. See [benchmarks §7](../benchmarks/README.md#7-outputs-and-the-comparison-notebook).

For the live DeepSeek V4 Pro deployment, follow the [performance runbook](../deployments/05-deepseek-v4-pro-h200/PERFORMANCE.md). The notebook includes concurrency sweep curves as well as the existing one-concurrency comparisons. Set `DISAGG_RESULTS` to the dedicated performance folder before running its loading cell.

[deepseek_v4_pro_256k.ipynb](deepseek_v4_pro_256k.ipynb) is the matched 256K-input H200 comparison. It audits identical request bodies and plots whole-run metrics plus first-turn/follow-up latency. See the [experiment protocol](../deployments/05-deepseek-v4-pro-h200/BENCHMARK-256K.md).
