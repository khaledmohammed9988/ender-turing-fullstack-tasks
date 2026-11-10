#!/bin/bash
set -Eeuo pipefail
cd /work/ender
mkdir -p .evidence
test -d /tmp/ender-infra-venv || uv venv /tmp/ender-infra-venv
uv pip install --python /tmp/ender-infra-venv/bin/python -r infrastructure/requirements.txt
/tmp/ender-infra-venv/bin/python -m pytest infrastructure/tests -q --junitxml=.evidence/infrastructure-junit.xml | tee .evidence/infrastructure-tests.txt
/tmp/ender-infra-venv/bin/python infrastructure/stack.py > /tmp/ender-stack.json
/tmp/ender-infra-venv/bin/cfn-lint /tmp/ender-stack.json | tee .evidence/cfn-lint.txt
shellcheck infrastructure/bootstrap.sh | tee .evidence/shellcheck.txt
test -f /tmp/ender-compose || curl -fsSL --retry 3 https://github.com/docker/compose/releases/download/v2.39.4/docker-compose-linux-x86_64 -o /tmp/ender-compose
curl -fsSL --retry 3 https://github.com/docker/compose/releases/download/v2.39.4/checksums.txt -o /tmp/ender-compose-checksums
expected=$(awk '{sub(/^\*/, "", $2); if ($2=="docker-compose-linux-x86_64") print $1}' /tmp/ender-compose-checksums)
test -n "$expected"
echo "$expected  /tmp/ender-compose" | sha256sum --check
chmod +x /tmp/ender-compose
python - <<'PY'
import json,os,subprocess
from pathlib import Path
env=os.environ|json.loads(Path('infrastructure/images.lock.json').read_text())['images']
subprocess.run(['/tmp/ender-compose','-f','infrastructure/compose.yaml','config','--quiet'],env=env,check=True)
Path('.evidence/compose-validation.txt').write_text('Docker Compose v2.39.4: checksum verified; compose config --quiet passed. No containers or AWS resources started.\n')
PY
echo 'Infrastructure checks completed'
