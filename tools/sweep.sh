#!/usr/bin/env bash
set -euo pipefail
# Additional arguments are forwarded to benchmarks.run.
# Use a client host with ample RAM; 256K contexts create multi-MB requests.
for concurrency in ${CONCURRENCIES:-1 2 4 8}; do
  for repetition in $(seq 1 "${REPETITIONS:-3}"); do
    echo "concurrency=$concurrency repetition=$repetition"
    python -m benchmarks.run --concurrency "$concurrency" "$@"
  done
done
python -m benchmarks.collect
