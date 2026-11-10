# Live runtime verification — 10 November 2026

**Result:** seven live checks passed for Ghost/MySQL running in a private temporary Daytona Docker sandbox. This is separate from the original 90 automated tests and does not certify the AWS deployment script end to end.

| Live check | Result |
| --- | --- |
| Pinned Ghost and MySQL containers report healthy | Passed |
| Ghost content file and MySQL marker record survive restarting both services | Passed |
| Ghost/MySQL have no host ports; test gateway binds only 127.0.0.1:8080 | Passed |
| Independent Windows-side authenticated HTTPS request returns a real Ghost-generated page | Passed; page title Ghost |
| Same preview without a credential is denied | Passed; HTTP 401 |
| Admin, setup API and encoded admin path are blocked | Passed; HTTP 403 |
| Write request to the public preview is blocked | Passed; HTTP 403 |

## What actually ran

- Docker Engine 28.3.3 in a private Daytona sandbox: 2 CPUs, 4 GB RAM, 10 GB disk allowance. The daemon used a Unix socket rather than a public TCP listener.
- Docker Compose v2.39.4, downloaded from its official release and verified against the published SHA-256 manifest.
- The exact Ghost and MySQL digests in `infrastructure/images.lock.json`, using the original Compose services, file-mounted secrets, health checks and database network.
- An extra read-only Node gateway, using the same Ghost image's Node runtime, protected the unclaimed admin/setup endpoints. It exposed only a loopback port in the private sandbox for the Daytona proxy.
- A standard private Daytona preview credential remained on the independent local controller. It was not printed, stored in the report or shared with the application. The outside probe refused redirects and checked the Ghost generator tag, not merely an HTTP 200 response.
- Fresh test passwords stayed in the sandbox. Saved logs redact them. Test containers and volumes were removed; the outer controller then deleted the sandbox and its preview credentials locally.

## Failed attempt and limits

The first Cloudflare Quick Tunnel attempt could not register: connections to `api.trycloudflare.com` were reset. A separate Python HTTPS check from Daytona reproduced connection resets to that API. This establishes a failed network path, not its ultimate cause. No claim is made that Cloudflare blocked the account or that the production connector is broken.

The initial diagnostic harness also matched `api.trycloudflare.com` as though it were an issued preview hostname. That parser was corrected to accept the generated multiword preview pattern and to report registration errors directly. It did not turn the failed Cloudflare attempt into a pass; the failure is retained in the evidence.

With the user's explicit instruction to stay on Daytona, the successful outside access check used Daytona's authenticated preview proxy instead. Therefore these checks do **not** verify CloudFormation resource creation, AWS security groups, IAM permissions, SSM token retrieval, Amazon Linux cloud-init, or the named Cloudflare connector. The original AWS deployment command was not executed, and no AWS resources were created.

## Evidence

`runtime-validation.json` is the sanitized runtime audit suitable for review with the source. Additional local-only evidence is in `.evidence/runtime-evidence/`: the audit, redacted container logs, and the failed Cloudflare attempt's audit/network-error excerpt. `.evidence/runtime/external-probe.json` records the independent host result; the saved HTML identifies Ghost. No preview token or generated password is part of these reports.

The sandbox and temporary endpoint were removed after the checks. Nothing was published or submitted.
