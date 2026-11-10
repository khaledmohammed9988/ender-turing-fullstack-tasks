#!/usr/bin/env python3
"""Generate a plan by default. AWS resources are created only with --execute."""

import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from stack import build_template


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack-name", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--ghost-url", required=True)
    parser.add_argument("--tunnel-token-parameter", required=True)
    parser.add_argument(
        "--instance-type", choices=["t3.small", "t3.medium"], default="t3.small"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually provision a fresh stack of paid AWS resources",
    )
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9-]{0,127}", args.stack_name):
        parser.error("Invalid stack name")
    url = urlparse(args.ghost_url)
    if (
        not re.fullmatch(
            r"https://[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]", args.ghost_url
        )
        or not url.hostname
        or "." not in url.hostname
    ):
        parser.error(
            "Use an HTTPS hostname with no credentials, port, path, query or fragment"
        )
    if not re.fullmatch(r"/[a-zA-Z0-9_./-]+", args.tunnel_token_parameter):
        parser.error("Expected an SSM parameter path, never the token itself")
    return args


def parameters(args):
    return [
        {"ParameterKey": key, "ParameterValue": value}
        for key, value in {
            "GhostUrl": args.ghost_url,
            "TunnelTokenParameter": args.tunnel_token_parameter,
            "InstanceType": args.instance_type,
        }.items()
    ]


def apply(client, args, template):
    from botocore.exceptions import ClientError

    common = dict(
        StackName=args.stack_name,
        TemplateBody=json.dumps(template),
        Parameters=parameters(args),
        Capabilities=["CAPABILITY_IAM"],
    )
    try:
        client.describe_stacks(StackName=args.stack_name)
    except ClientError as error:
        message = error.response.get("Error", {}).get("Message", "")
        if (
            error.response.get("Error", {}).get("Code") != "ValidationError"
            or "does not exist" not in message
        ):
            raise
        response = client.create_stack(**common, OnFailure="ROLLBACK")
        client.get_waiter("stack_create_complete").wait(StackName=args.stack_name)
    else:
        # EC2 cloud-init does not automatically rerun changed user data. Avoid claiming
        # an application rollout from a CloudFormation-only update.
        raise RuntimeError(
            "Stack already exists. This exercise supports initial provisioning only. Use SSM to inspect it; review backups and a separate update plan before changing it."
        )
    return {
        "status": "infrastructure_ready",
        "stack_id": response["StackId"],
        "next": "Verify /opt/ender-ghost/bootstrap-complete through SSM, container health and tunnel HTTPS before declaring application readiness.",
    }


def verify_runtime(ssm, instance_id, *, sleep=time.sleep):
    from botocore.exceptions import ClientError

    command_id = None
    for _ in range(60):
        try:
            command_id = ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName="AWS-RunShellScript",
                TimeoutSeconds=900,
                Parameters={
                    "commands": [
                        "set -eu",
                        "for attempt in $(seq 1 60); do test -f /opt/ender-ghost/bootstrap-complete && break; sleep 10; done",
                        "test -f /opt/ender-ghost/bootstrap-complete || exit 1",
                        "cd /opt/ender-ghost && docker compose --env-file images.env ps --format json",
                        "docker compose --env-file images.env exec -T ghost node -e \"require('http').get('http://cloudflared:2000/ready',r=>process.exit(r.statusCode===200?0:1)).on('error',()=>process.exit(1))\"",
                    ]
                },
            )["Command"]["CommandId"]
            break
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") not in {
                "InvalidInstanceId",
                "TargetNotConnected",
            }:
                raise
            sleep(10)
    if command_id is None:
        raise RuntimeError(
            "SSM did not become available; inspect the stack and EC2 console before retrying"
        )
    for _ in range(120):
        try:
            result = ssm.get_command_invocation(
                CommandId=command_id, InstanceId=instance_id
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") != "InvocationDoesNotExist":
                raise
            sleep(5)
            continue
        if result["Status"] == "Success":
            return {
                "status": "vm_bootstrap_and_containers_verified",
                "instance_id": instance_id,
                "next": "Confirm the configured HTTPS hostname and claim the Ghost owner account before sharing the URL.",
            }
        if result["Status"] in {"Failed", "Cancelled", "TimedOut", "Cancelling"}:
            # A failed marker check may just mean cloud-init is still downloading images.
            raise RuntimeError(
                "Bootstrap marker not ready. Inspect cloud-init with SSM; rerun after it completes."
            )
        sleep(5)
    raise RuntimeError("Timed out waiting for the SSM runtime check")


def main(argv=None):
    args = arguments(argv)
    template = build_template()
    state = Path(__file__).resolve().parent / ".state"
    state.mkdir(exist_ok=True)
    (state / "stack.json").write_text(json.dumps(template, indent=2))
    plan = {
        "mode": "execute" if args.execute else "plan_only",
        "stack": args.stack_name,
        "region": args.region,
        "parameters": parameters(args),
        "resources": len(template["Resources"]),
        "warning": "EC2, EBS and public IPv4 incur charges when executed. No resources are created without --execute.",
    }
    print(json.dumps(plan, indent=2))
    if args.execute:
        import boto3

        cfn = boto3.client("cloudformation", region_name=args.region)
        print(json.dumps(apply(cfn, args, template), indent=2))
        outputs = cfn.describe_stacks(StackName=args.stack_name)["Stacks"][0]["Outputs"]
        instance_id = next(
            x["OutputValue"] for x in outputs if x["OutputKey"] == "InstanceId"
        )
        print(
            json.dumps(
                verify_runtime(
                    boto3.client("ssm", region_name=args.region), instance_id
                ),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
