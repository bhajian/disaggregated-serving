#!/usr/bin/env bash
set -euo pipefail
# render: no cluster writes. install: installs the chart into an existing namespace.
action=${1:?Usage: llmd-router.sh render|install MANIFEST_DIRECTORY}
directory=${2:?Pass the rendered llm-d directory}
chart=oci://ghcr.io/llm-d/charts/llm-d-router-standalone
version=v0.11.0
case "$action" in
  render)
    helm template llmd "$chart" --version "$version" --namespace llm-d \
      -f "$directory/router/values.yaml" > "$directory/router/rendered.yaml"
    ;;
  install)
    helm upgrade --install llmd "$chart" --version "$version" --namespace llm-d \
      -f "$directory/router/values.yaml" --wait --timeout 15m
    ;;
  *) echo 'Expected render or install' >&2; exit 2 ;;
esac
