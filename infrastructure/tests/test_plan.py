import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deploy import arguments, main
from stack import build_template


def test_no_direct_ingress_and_no_ssh_keys_or_host_ports():
    template = build_template()
    resources = template["Resources"]
    assert resources["NoIngress"]["Properties"]["SecurityGroupIngress"] == []
    instance = resources["GhostVm"]["Properties"]
    assert "KeyName" not in instance
    assert instance["MetadataOptions"]["HttpTokens"] == "required"
    assert instance["BlockDeviceMappings"][0]["Ebs"]["Encrypted"] is True
    assert not any(
        r["Type"] == "AWS::EC2::SecurityGroupIngress" for r in resources.values()
    )
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text())
    for service in compose["services"].values():
        assert "ports" not in service
        assert service.get("network_mode") != "host"
    assert compose["networks"]["database"]["internal"] is True
    assert compose["services"]["cloudflared"]["command"][-2:] == [
        "--token-file",
        "/run/secrets/tunnel_token",
    ]


def test_images_are_immutable_and_secrets_are_files():
    lock = json.loads((ROOT / "images.lock.json").read_text())
    assert set(lock["images"]) == {"GHOST_IMAGE", "MYSQL_IMAGE", "CLOUDFLARED_IMAGE"}
    for value in lock["images"].values():
        assert "@sha256:" in value and len(value.split("@sha256:")[1]) == 64
    template = build_template()
    assert "NoEcho" not in json.dumps(
        template
    )  # no secret-valued stack parameter at all
    policies = template["Resources"]["InstanceRole"]["Properties"]["Policies"]
    token = policies[0]["PolicyDocument"]["Statement"][0]
    assert token["Action"] == "ssm:GetParameter"
    assert token["Resource"] != "*"
    assert "ssm:GetParameters" not in json.dumps(policies)


@pytest.mark.parametrize(
    "url",
    [
        "http://blog.example.com",
        "https://x.example/a",
        "https://user:pass@x.example",
        "https://x.example?x=1",
        "https://x.example';touch /tmp/bad",
    ],
)
def test_untrusted_url_cannot_be_injected_into_user_data(url):
    with pytest.raises(SystemExit):
        arguments(
            [
                "--stack-name",
                "review",
                "--region",
                "us-east-1",
                "--ghost-url",
                url,
                "--tunnel-token-parameter",
                "/review/token",
            ]
        )


def test_default_plan_does_not_load_aws_sdk_or_create_resources(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "boto3", None)
    main(
        [
            "--stack-name",
            "review",
            "--region",
            "us-east-1",
            "--ghost-url",
            "https://blog.example.com",
            "--tunnel-token-parameter",
            "/review/token",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "plan_only"
    assert output["resources"] > 0


def test_rendered_bootstrap_has_valid_shell_syntax_and_no_interpolated_secret(tmp_path):
    parts = build_template()["Resources"]["GhostVm"]["Properties"]["UserData"][
        "Fn::Base64"
    ]["Fn::Join"][1]
    values = {
        "AWS::Region": "us-east-1",
        "TunnelTokenParameter": "/review/token",
        "GhostUrl": "https://blog.example.com",
    }
    script = "".join(values[p["Ref"]] if isinstance(p, dict) else p for p in parts)
    path = tmp_path / "bootstrap.sh"
    path.write_text(script)
    subprocess.run(["bash", "-n", str(path)], check=True)
    assert "ssm get-parameter" in script
    assert "systemctl mask --now sshd" in script
    assert "--with-decryption" in script
    assert "set -x" not in script
