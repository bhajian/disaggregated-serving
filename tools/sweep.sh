#!/usr/bin/env bash
set -euo pipefail
# Additional arguments are forwarded to benchmarks.run.
# Use a client host with ample RAM; 256K contexts create multi-MB requests.
args=("$@")
results_dir=results
while (( $# )); do
  case "$1" in
    --results) results_dir="${2:?--results requires a directory}"; shift ;;
    --results=*) results_dir="${1#--results=}" ;;
  esac
  shift
done
for concurrency in ${CONCURRENCIES:-1 2 4 8}; do
  for repetition in $(seq 1 "${REPETITIONS:-3}"); do
    echo "concurrency=$concurrency repetition=$repetition"
    python -m benchmarks.run --concurrency "$concurrency" "${args[@]}"
  done
done
python -m benchmarks.collect --results "$results_dir"
