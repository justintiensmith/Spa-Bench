#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export THROUGHPUT_PROBE=1
export PROBE_STEPS="${PROBE_STEPS:-50}"
export PROBE_SAVE_INTERVAL="${PROBE_SAVE_INTERVAL:-25}"
exec "${SCRIPT_DIR}/train_fsdp_4gpu.sh"
