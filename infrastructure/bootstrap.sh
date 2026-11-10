#!/bin/bash
set -Eeuo pipefail
umask 077
trap 'echo "Ghost bootstrap failed at line $LINENO; inspect /var/log/cloud-init-output.log" >&2' ERR

# This script runs as EC2 cloud-init, never on the reviewer's workstation.
dnf install -y docker python3
systemctl enable --now docker
systemctl mask --now sshd
install -d -m 0700 /opt/ender-ghost /opt/ender-ghost/.secrets
cd /opt/ender-ghost
rm -f /opt/ender-ghost/bootstrap-complete

# Compose is installed from the upstream release and verified by its published checksum.
compose_version=v2.39.4
compose_asset=docker-compose-linux-x86_64
compose_base="https://github.com/docker/compose/releases/download/$compose_version"
install -d /usr/local/lib/docker/cli-plugins
curl --fail --location --retry 3 "$compose_base/$compose_asset" -o "/tmp/$compose_asset"
curl --fail --location --retry 3 "$compose_base/checksums.txt" -o /tmp/compose-checksums.txt
(cd /tmp && grep -E " [*]?$compose_asset$" compose-checksums.txt | sha256sum --check --status)
install -m 0755 "/tmp/$compose_asset" /usr/local/lib/docker/cli-plugins/docker-compose

aws ssm get-parameter --name "$TUNNEL_TOKEN_PARAMETER" --with-decryption \
  --query Parameter.Value --output text > .secrets/tunnel_token
test -s .secrets/tunnel_token

python3 - <<'PY'
import json, os, secrets
from pathlib import Path
secret_dir=Path('.secrets')
for filename in ('db_password','db_root_password'):
    path=secret_dir/filename
    if not path.exists():
        path.write_text(secrets.token_hex(32))
config={
    'url':os.environ['GHOST_URL'],
    'server':{'port':2368,'host':'0.0.0.0'},
    'database':{'client':'mysql','connection':{
        'host':'db','user':'ghost','password':(secret_dir/'db_password').read_text().strip(),'database':'ghost'
    }},
    'logging':{'transports':['stdout']},
}
(secret_dir/'ghost_config.json').write_text(json.dumps(config))
# Parent directory stays 0700 on the host; containers need to read their mounted files.
for path in secret_dir.iterdir():
    path.chmod(0o444)
PY

docker compose --env-file images.env config --quiet
docker compose --env-file images.env up -d --wait --wait-timeout 600
docker compose --env-file images.env ps
for _attempt in $(seq 1 60); do
  if docker compose --env-file images.env exec -T ghost node -e \
    "require('http').get('http://cloudflared:2000/ready',r=>process.exit(r.statusCode===200?0:1)).on('error',()=>process.exit(1))"; then
    touch /opt/ender-ghost/bootstrap-complete
    exit 0
  fi
  sleep 5
done
echo 'Cloudflare tunnel did not become ready' >&2
exit 1
