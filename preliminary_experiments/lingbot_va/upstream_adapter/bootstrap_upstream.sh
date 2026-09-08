#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
UPSTREAM_DIR="${UPSTREAM_DIR:-/vol/dissolve/justin/src/lingbot-va}"
UPSTREAM_COMMIT="7c6ffa9bfc4b83582cafc860fab4c82cc7deeeeb"

if [[ ! -d "${UPSTREAM_DIR}/.git" ]]; then
  mkdir -p "$(dirname -- "${UPSTREAM_DIR}")"
  git clone https://github.com/Robbyant/lingbot-va.git "${UPSTREAM_DIR}"
fi

CURRENT_COMMIT="$(git -C "${UPSTREAM_DIR}" rev-parse HEAD)"
if [[ "${CURRENT_COMMIT}" != "${UPSTREAM_COMMIT}" ]]; then
  echo "ERROR: ${UPSTREAM_DIR} is at ${CURRENT_COMMIT}, expected ${UPSTREAM_COMMIT}." >&2
  echo "Use a fresh UPSTREAM_DIR; this script will not reset an existing checkout." >&2
  exit 1
fi

python "${SCRIPT_DIR}/install_upstream_adapter.py" --upstream-dir "${UPSTREAM_DIR}"
git -C "${UPSTREAM_DIR}" diff --check

echo "Pinned upstream checkout is ready: ${UPSTREAM_DIR}"
echo "Install its pinned requirements in a Python 3.10 / PyTorch 2.9 environment before training."
