#!/bin/bash
# Disposable cloud sandbox only. Never run this on a workstation or production VM.
set -Eeuo pipefail
test "${ENDER_DISPOSABLE_SANDBOX:-}" = yes || { echo 'Set ENDER_DISPOSABLE_SANDBOX=yes only in an isolated Linux sandbox' >&2; exit 1; }
test "$(id -u)" = 0
cd /work/ender
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq postgresql curl unzip shellcheck
python -m pip install --quiet uv
curl -fsSL --retry 3 https://github.com/oven-sh/bun/releases/download/bun-v1.4.4/bun-linux-x64.zip -o /tmp/bun.zip
unzip -q -o /tmp/bun.zip -d /tmp/bun
install -D -m 0755 /tmp/bun/bun-linux-x64/bun /root/.bun/bin/bun
uv sync --frozen --package app --group dev
bash scripts/validate-cloud.sh
