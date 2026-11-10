"""Install the pinned Compose executable in the disposable controller container only."""
import hashlib
import shutil
import time
import urllib.request
from pathlib import Path

base = 'https://github.com/docker/compose/releases/download/v2.39.4/'
name = 'docker-compose-linux-x86_64'
target = Path.home() / '.docker/cli-plugins/docker-compose'
target.parent.mkdir(parents=True, exist_ok=True)
for attempt in range(3):
    try:
        with urllib.request.urlopen(base + 'checksums.txt', timeout=60) as response:
            lines = response.read().decode().splitlines()
        expected = next(line.split()[0] for line in lines if line.split()[1].lstrip('*') == name)
        with urllib.request.urlopen(base + name, timeout=90) as response, target.open('wb') as output:
            shutil.copyfileobj(response, output)
        assert hashlib.sha256(target.read_bytes()).hexdigest() == expected, 'Compose checksum mismatch'
        target.chmod(0o755)
        print('Compose v2.39.4 installed and SHA-256 verified', flush=True)
        break
    except Exception:
        if attempt == 2: raise
        time.sleep(3)
