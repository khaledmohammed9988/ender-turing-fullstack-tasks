"""Live container/tunnel check in a disposable cloud sandbox; never calls AWS."""
import json
import os
import re
import secrets
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WORK = Path('/tmp/ender-ghost-runtime')
EVIDENCE = Path('/work/ender/runtime-evidence')


def main():
    if os.environ.get('ENDER_DISPOSABLE_SANDBOX') != 'yes':
        raise SystemExit('Only run in an explicitly designated disposable cloud sandbox')
    EVIDENCE.mkdir(exist_ok=True)
    WORK.mkdir(mode=0o700, exist_ok=True)
    secret_dir = WORK / '.secrets'
    secret_dir.mkdir(mode=0o700, exist_ok=True)
    for name in ('db_password', 'db_root_password'):
        (secret_dir / name).write_text(secrets.token_hex(32))
    preview_mode = os.environ.get('ENDER_TUNNEL_PROVIDER') == 'daytona'
    preview_url = Path('/work/ender/preview-url.txt').read_text().strip() if preview_mode else None
    config = {
        'url': preview_url or 'http://ghost:2368',
        'server': {'port': 2368, 'host': '0.0.0.0'},
        'database': {'client': 'mysql', 'connection': {
            'host': 'db', 'user': 'ghost', 'password': (secret_dir / 'db_password').read_text(), 'database': 'ghost'
        }}, 'logging': {'transports': ['stdout']},
    }
    config_path = secret_dir / 'ghost_config.json'
    config_path.write_text(json.dumps(config))
    for path in secret_dir.iterdir():
        path.chmod(0o444)
    images = json.loads((ROOT / 'images.lock.json').read_text())['images']
    (WORK / 'images.env').write_text(''.join(f'{k}={v}\n' for k, v in images.items()))
    compose = yaml.safe_load((ROOT / 'compose.yaml').read_text())
    # Keep the real Ghost/MySQL services unchanged; use a token-free quick tunnel and
    # an extra read-only gateway because this test has no production CF account.
    del compose['secrets']['tunnel_token']
    tunnel = compose['services']['cloudflared']
    del tunnel['secrets']
    tunnel['command'] = ['tunnel', '--no-autoupdate', '--metrics', '0.0.0.0:2000',
                         '--url', 'http://gateway:8080', '--protocol', 'http2']
    tunnel['depends_on'] = {'gateway': {'condition': 'service_started'}}
    tunnel['restart'] = 'no'
    shutil.copyfile(HERE / 'gateway.js', WORK / 'gateway.js')
    compose['services']['gateway'] = {
        'image': '${GHOST_IMAGE}', 'entrypoint': ['node', '/smoke/gateway.js'],
        'volumes': ['./gateway.js:/smoke/gateway.js:ro'], 'networks': ['tunnel'],
        'depends_on': {'ghost': {'condition': 'service_healthy'}},
        'read_only': True, 'cap_drop': ['ALL'],
        'security_opt': ['no-new-privileges:true'],
    }
    if preview_mode:
        del compose['services']['cloudflared']
        compose['services']['gateway']['ports'] = ['127.0.0.1:8080:8080']
    (WORK / 'compose.yaml').write_text(yaml.safe_dump(compose, sort_keys=False))
    command = ['docker', 'compose', '--project-name', 'ender-runtime-smoke', '--env-file', 'images.env']

    def dc(*args, capture=False, timeout=900):
        return subprocess.run(command + list(args), cwd=WORK, check=True,
                              stdout=subprocess.PIPE if capture else None,
                              stderr=subprocess.STDOUT if capture else None,
                              text=True, timeout=timeout)

    def fetch(url, method='GET'):
        request = urllib.request.Request(url, method=method, headers={'User-Agent': 'Ender-Disposable-Smoke/1.0'})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, response.read().decode(errors='replace'), dict(response.headers)
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode(errors='replace'), dict(error.headers)

    audit = {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'provider': 'Daytona temporary sandbox',
             'aws_cloudformation_executed': False, 'named_cloudflare_token_tested': False,
             'tunnel_provider': 'Daytona authenticated preview proxy' if preview_mode else 'Cloudflare Quick Tunnel',
             'images': images, 'changes_from_deployment': ['Authenticated Daytona preview instead of Cloudflare connector' if preview_mode else 'Quick Tunnel instead of named-token connector',
             'Read-only gateway blocks admin/setup and writes', 'No AWS IAM/SSM/cloud-init'], 'checks': {}}
    try:
        dc('config', '--quiet')
        dc('up', '-d', '--wait', '--wait-timeout', '600', 'db', 'ghost', 'gateway')
        audit['checks']['ghost_and_mysql_healthy'] = True
        if preview_mode:
            dc('exec', '-T', 'ghost', 'node', '-e', "require('fs').writeFileSync('/var/lib/ghost/content/smoke-sentinel.txt','runtime-review')")
            dc('exec', '-T', 'db', 'sh', '-c', 'MYSQL_PWD="$(cat /run/secrets/db_password)" mysql -ughost ghost -e "CREATE TABLE ender_smoke_marker (value VARCHAR(40)); INSERT INTO ender_smoke_marker VALUES (\'runtime-review\');"')
            dc('restart', 'db', 'ghost')
            dc('up', '-d', '--wait', '--wait-timeout', '300', 'db', 'ghost', 'gateway')
            dc('exec', '-T', 'ghost', 'node', '-e', "if(require('fs').readFileSync('/var/lib/ghost/content/smoke-sentinel.txt','utf8')!=='runtime-review')process.exit(1)")
            marker = dc('exec', '-T', 'db', 'sh', '-c', 'MYSQL_PWD="$(cat /run/secrets/db_password)" mysql -ughost ghost -Nse "SELECT value FROM ender_smoke_marker;"', capture=True).stdout.strip()
            assert marker == 'runtime-review'
            audit['checks']['ghost_content_and_mysql_record_persisted_after_restart'] = True
            containers = json.loads(subprocess.check_output(['docker', 'inspect'] + dc('ps', '-q', capture=True).stdout.split(), text=True))
            audit['containers'] = [{'name':c['Name'], 'image_id':c['Image'], 'state':c['State']['Status'],
                'health':c['State'].get('Health',{}).get('Status'), 'published_ports':c['HostConfig'].get('PortBindings') or {}} for c in containers]
            for container in audit['containers']:
                if 'gateway' in container['name']:
                    bindings=container['published_ports']['8080/tcp']
                    assert all(b['HostIp']=='127.0.0.1' for b in bindings)
                else:
                    assert not container['published_ports']
            audit['checks']['only_gateway_loopback_port_no_ghost_or_mysql_host_ports'] = True
            (EVIDENCE/'awaiting-external-probe.json').write_text(json.dumps({'status':'ready'}))
            result_path=Path('/work/ender/runtime-external-probe.json')
            for _ in range(90):
                if result_path.exists(): break
                time.sleep(2)
            if not result_path.exists(): raise RuntimeError('Timed out waiting for independent external HTTPS probe')
            external=json.loads(result_path.read_text())
            audit['external_probe']=external
            assert external['status']=='passed', 'External HTTPS probe failed'
            audit['checks'].update(external['checks'])
            audit['status']='passed'
            print('Daytona live runtime and independent authenticated HTTPS checks passed',flush=True)
            return
        dc('up', '-d', 'cloudflared')
        url = None
        for _ in range(90):
            logs = dc('logs', '--no-color', 'cloudflared', capture=True).stdout
            match = re.search(r'https://[a-z0-9]+(?:-[a-z0-9]+){2,}\.trycloudflare\.com', logs)
            if match:
                url = match.group(); break
            if 'failed to request quick Tunnel' in logs:
                raise RuntimeError('Cloudflare Quick Tunnel registration failed; inspect the recorded network error')
            time.sleep(2)
        if not url:
            raise RuntimeError('Quick Tunnel URL did not become available')
        config['url'] = url
        config_path.write_text(json.dumps(config))
        dc('restart', 'ghost')
        dc('up', '-d', '--wait', '--wait-timeout', '300', 'db', 'ghost', 'gateway')
        for attempt in range(60):
            try:
                status, body, headers = fetch(url)
                if status == 200 and '<html' in body.lower(): break
            except (OSError, urllib.error.URLError): pass
            if attempt == 59: raise RuntimeError('Public HTTPS Ghost page did not become healthy')
            time.sleep(3)
        audit['checks']['public_https_home'] = {'status': status, 'html': '<html' in body.lower(),
                                               'ghost_generator': 'Ghost' in body}
        (EVIDENCE / 'home.html').write_text(body)
        for path in ('/ghost/', '/ghost/api/admin/authentication/setup/', '/%67host/'):
            status, _, _ = fetch(url + path)
            assert status == 403, f'Admin restriction failed for {path}: {status}'
        audit['checks']['admin_and_encoded_admin_denied'] = True
        status, _, _ = fetch(url + '/', method='POST')
        assert status == 403
        audit['checks']['public_writes_denied'] = True
        containers = json.loads(subprocess.check_output(['docker', 'inspect'] + dc('ps', '-q', capture=True).stdout.split(), text=True))
        audit['containers'] = [{
            'name': c['Name'], 'image_id': c['Image'], 'state': c['State']['Status'],
            'health': c['State'].get('Health', {}).get('Status'),
            'published_ports': c['HostConfig'].get('PortBindings') or {},
        } for c in containers]
        assert all(not c['published_ports'] for c in audit['containers'])
        audit['checks']['no_host_published_ports'] = True
        # Verify a harmless sentinel in Ghost content and the MySQL database survive restart.
        dc('exec', '-T', 'ghost', 'node', '-e', "require('fs').writeFileSync('/var/lib/ghost/content/smoke-sentinel.txt','runtime-review')")
        dc('restart', 'db', 'ghost')
        dc('up', '-d', '--wait', '--wait-timeout', '300', 'db', 'ghost', 'gateway')
        dc('exec', '-T', 'ghost', 'node', '-e', "if(require('fs').readFileSync('/var/lib/ghost/content/smoke-sentinel.txt','utf8')!=='runtime-review')process.exit(1)")
        for attempt in range(30):
            try:
                status, _, _ = fetch(url)
                if status == 200: break
            except OSError: pass
            if attempt == 29: raise RuntimeError('Ghost did not recover after database/application restart')
            time.sleep(3)
        audit['checks']['content_and_database_restart'] = True
        audit['temporary_url'] = url
        audit['status'] = 'passed'
        print('Runtime checks passed: public HTTPS, blocked admin/writes, no host ports, persistence/recovery')
    except Exception as error:
        audit['status'] = 'failed'
        audit['error'] = str(error)
        raise
    finally:
        try:
            logs=dc('logs', '--no-color', '--tail', '100', capture=True).stdout
            for name in ('db_password','db_root_password'):
                logs=logs.replace((secret_dir/name).read_text().strip(),'[REDACTED]')
            (EVIDENCE / 'compose-logs.txt').write_text(logs)
        except Exception: pass
        try:
            dc('down', '--volumes', '--remove-orphans', timeout=120)
            audit['containers_and_test_volumes_removed'] = True
        except Exception:
            audit['containers_and_test_volumes_removed'] = False
        audit['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        (EVIDENCE / 'runtime-audit.json').write_text(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
