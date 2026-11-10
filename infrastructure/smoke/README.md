# Disposable live runtime check

This harness runs the pinned Ghost and MySQL containers from the real Compose file in a temporary Daytona Docker sandbox. It is separate from the AWS provisioning command. It never calls CloudFormation, IAM or SSM.

The first Cloudflare Quick Tunnel attempt encountered outbound connection resets from Daytona. The follow-up mode uses Daytona's authenticated HTTPS preview proxy. This does not certify the production named Cloudflare connector.

## Scope and safeguards

- Use an isolated, private, disposable Linux sandbox with Docker Engine. The executed environment uses Docker 28.3.3, 2 CPUs, 4 GB RAM and a 10 GB sandbox disk.
- `prepare.py` downloads Docker Compose v2.39.4 from the official GitHub release and verifies its SHA-256 manifest. Run it inside the disposable controller, not on a workstation.
- `run.py` refuses to proceed unless `ENDER_DISPOSABLE_SANDBOX=yes` is explicitly set.
- The test generates fresh database passwords. Files stay in the sandbox and are never copied into the repository or report. Test logs redact the generated passwords.
- Ghost and MySQL keep their original images, file-mounted secrets, health checks and isolated database network. The test adds a read-only Node gateway that rejects admin/setup routes, encoded admin routes and all write methods.
- In `ENDER_TUNNEL_PROVIDER=daytona` mode, only the gateway is bound to `127.0.0.1:8080` in the private sandbox. Ghost/MySQL have no host port mappings. The sandbox remains private; external requests require the preview credential.
- The standard preview token is a sandbox credential. Keep it solely in the local controller, send it only in the provider authentication header, and never store it in a library, public report or application container. An independent probe must refuse redirects to avoid forwarding credentials to another host.
- The harness creates a Ghost content sentinel and a MySQL marker record, restarts both services, then verifies both markers. An independent Windows-side probe checks real HTTPS, the Ghost generator tag, denied anonymous access, rejected admin/setup URLs and rejected writes.
- The outside probe writes a sanitized result to `/work/ender/runtime-external-probe.json`; it contains no token. The harness waits at most three minutes for this result, then tears down test containers and volumes. The outer controller deletes the entire sandbox after evidence is saved.

## Running

1. Create a private Docker-capable Daytona sandbox and start Docker with its Unix socket only. Upload this repository's `infrastructure/` source, not local credentials or environment files.
2. Obtain a private preview for port 8080 with the SDK's `get_preview_link(8080)`. Write only its non-secret `url` to `/work/ender/preview-url.txt`. Keep its `token` on the independent controller.
3. Run the harness in a Python controller container with PyYAML, the Docker CLI/socket, and shared `/work/ender` and `/tmp/ender-ghost-runtime` paths. Set `ENDER_DISPOSABLE_SANDBOX=yes` and `ENDER_TUNNEL_PROVIDER=daytona`.
4. Once `runtime-evidence/awaiting-external-probe.json` appears, make the outside HTTPS checks using the private token header and write the sanitized result file. Do not share or print the credential.
5. Save `runtime-evidence/runtime-audit.json` and sanitized logs, then delete the sandbox. Successful component checks do not change the fact that the AWS deployment path and named Cloudflare tunnel remain untested.

Documentation: [Daytona preview authentication](https://www.daytona.io/docs/en/preview/), [Daytona Docker support](https://www.daytona.io/docs/docker/), [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).
