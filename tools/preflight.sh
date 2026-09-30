#!/usr/bin/env bash
set -euo pipefail
# Run on each GPU host. Checks host inventory; actual RDMA/inference is separate.
model_dir=${1:?Usage: preflight.sh MODEL_DIRECTORY [IP_INTERFACE]}
iface=${2:-eth0}
hostname
ip -4 -br addr show dev "$iface"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
test "$(nvidia-smi --query-gpu=index --format=csv,noheader | wc -l)" -eq 8
test -d /dev/infiniband
test -s "$model_dir/config.json"
test -s "$model_dir/DEPLOYED_REVISION"
cat "$model_dir/DEPLOYED_REVISION"
df -h "$model_dir"
free -h
ulimit -l
echo 'Compare revision on both nodes; run ib_write_bw on all intended port pairs before inference.'
