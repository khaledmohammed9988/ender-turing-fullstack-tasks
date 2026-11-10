# Task 2: Ghost on an AWS VM through Cloudflare Tunnel

One command provisions a fresh AWS CloudFormation stack, waits for the VM, then checks bootstrap completion and tunnel readiness through SSM. The default command is **plan-only**. No real AWS deployment was performed during preparation.

A separate live Daytona test passed seven runtime checks for the pinned Ghost/MySQL images, persistence after restart and private HTTPS access. Cloudflare Quick Tunnel registration failed with connection resets, so the successful access test used Daytona's authenticated preview proxy with a read-only gateway. This is not an AWS or named-Cloudflare deployment receipt. See `../docs/runtime-validation.md`.

## Prerequisites

1. Python 3.12+ and the dependencies in `requirements.txt`.
2. An AWS account and an operator identity permitted to create the stack resources and IAM instance role, pass that role to EC2, use the regional public AL2023 AMI parameter, and run/inspect SSM commands. Select a region with the chosen instance type available. Account-level permissions and quotas are not created by the script.
3. An existing Cloudflare-managed tunnel and HTTPS DNS hostname. Configure that hostname's service as **`http://ghost:2368`**. Protect `/ghost` with Cloudflare Access while claiming the owner account.
4. Store the tunnel token, separately, in an existing **SSM SecureString** parameter such as `/ender-review/cloudflare-token`, in the selected AWS region. Use the AWS-managed SSM KMS key. A customer-managed KMS key requires an additional, narrowly scoped decrypt grant. Never pass the token as a command-line argument or commit it.

## Plan and execute

```sh
python -m venv .venv-infra
# Activate that environment, then:
python -m pip install -r infrastructure/requirements.txt
python infrastructure/deploy.py --stack-name ender-ghost-review --region eu-west-1 \
  --ghost-url https://blog.example.com --tunnel-token-parameter /ender-review/cloudflare-token
```

Review `infrastructure/.state/stack.json`. The command above does not contact AWS. After human approval, add **`--execute`** to the same command to create paid resources. It can take several minutes. This is initial provisioning only; an existing stack is refused. A failed readiness check leaves resources available for inspection rather than deleting data automatically.

The VM uses Amazon Linux 2023, Docker Compose, Ghost, MySQL and cloudflared. `images.lock.json` records immutable image digests and the original source tags. Compose v2.39.4 is downloaded from the official release and checked against its published SHA-256 manifest.

## Access and verification

- Security group: zero ingress rules; no SSH key; sshd disabled; IMDSv2 required; encrypted EBS.
- There are no Docker host port mappings. MySQL is on an internal Docker network; only Ghost and cloudflared share the tunnel network.
- Instance IAM can read the exact token parameter and open SSM management channels. The operator, not the VM, has CloudFormation provisioning permissions.
- The token and database credentials are root-managed files, not user-data secrets or environment values. The host secret directory is mode 0700; mounted files are readable by their container processes.
- Bootstrap waits for MySQL and Ghost health, then cloudflared's internal `/ready` endpoint. The deployment command rechecks the marker and tunnel readiness through SSM. Also visit the external HTTPS URL, claim Ghost's owner account, and verify admin protection yourself.
- If provisioning fails, inspect CloudFormation events and use SSM Session Manager to inspect `/var/log/cloud-init-output.log` and `/opt/ender-ghost`. Do not enable SSH as a workaround or share logs before checking them for secrets.

## Cost, recovery and teardown

EC2, EBS and public IPv4 incur charges. There is no NAT gateway or load balancer. Do not execute merely to generate a screenshot. Back up both Docker volumes before terminating the instance. With reviewed backups, delete the stack through CloudFormation; this deletes its root volume and application data. The pre-existing tunnel, DNS and SSM token parameter are not owned by the stack and must be managed separately.

The instance's public IP enables outbound Internet access; security groups still block unsolicited inbound traffic. Egress is unrestricted. This exercise does not include automated upgrades, backups, SMTP or high availability.

## Offline checks

```sh
python -m pytest infrastructure/tests -q
python infrastructure/stack.py > /tmp/ender-stack.json
cfn-lint /tmp/ender-stack.json
shellcheck infrastructure/bootstrap.sh
```

`scripts/validate-infrastructure.sh` additionally verifies the Compose binary checksum and parses the rendered Compose configuration in an isolated Linux environment. It does not start containers or create cloud resources. Unit tests mock AWS responses; they are not a deployment receipt.
