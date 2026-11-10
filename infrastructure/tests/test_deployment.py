import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deploy import apply, verify_runtime


def error(code, message):
    return ClientError({"Error": {"Code": code, "Message": message}}, "test")


class FakeCloudFormation:
    def __init__(self, mode):
        self.mode = mode
        self.calls = []

    def describe_stacks(self, **kwargs):
        if self.mode == "new":
            raise error("ValidationError", "Stack review does not exist")
        if self.mode == "denied":
            raise error("AccessDenied", "Not authorized")
        return {"Stacks": [{}]}

    def create_stack(self, **kwargs):
        self.calls.append(("create", kwargs))
        return {"StackId": "local-test-stack"}

    def update_stack(self, **kwargs):
        self.calls.append(("update", kwargs))
        if self.mode == "unchanged":
            raise error("ValidationError", "No updates are to be performed.")
        return {"StackId": "local-test-stack"}

    def get_waiter(self, name):
        self.calls.append(("waiter", name))
        return SimpleNamespace(wait=lambda **kwargs: None)


def test_create_waits_for_infrastructure():
    mode, expected = "new", "create"
    client = FakeCloudFormation(mode)
    args = SimpleNamespace(
        stack_name="review",
        ghost_url="https://blog.example.com",
        tunnel_token_parameter="/review/token",
        instance_type="t3.small",
    )
    result = apply(client, args, {"Resources": {}})
    assert client.calls[0][0] == expected
    assert "CAPABILITY_IAM" in client.calls[0][1]["Capabilities"]
    assert result["status"] == "infrastructure_ready"


@pytest.mark.parametrize("mode", ["existing", "unchanged"])
def test_existing_stack_is_not_silently_updated(mode):
    client = FakeCloudFormation(mode)
    args = SimpleNamespace(
        stack_name="review",
        ghost_url="https://blog.example.com",
        tunnel_token_parameter="/review/token",
        instance_type="t3.small",
    )
    with pytest.raises(RuntimeError, match="initial provisioning only"):
        apply(client, args, {"Resources": {}})
    assert client.calls == []


def test_permission_error_is_not_misread_as_missing_stack():
    client = FakeCloudFormation("denied")
    with pytest.raises(ClientError):
        apply(
            client,
            SimpleNamespace(
                stack_name="review",
                ghost_url="https://blog.example.com",
                tunnel_token_parameter="/review/token",
                instance_type="t3.small",
            ),
            {},
        )
    assert client.calls == []


def test_runtime_check_waits_for_agent_and_does_not_report_early_success():
    class SSM:
        attempts = 0

        def send_command(self, **kwargs):
            self.attempts += 1
            if self.attempts == 1:
                raise error("InvalidInstanceId", "Agent is not registered yet")
            assert any(
                "bootstrap-complete" in c for c in kwargs["Parameters"]["commands"]
            )
            assert any(
                "cloudflared:2000/ready" in c for c in kwargs["Parameters"]["commands"]
            )
            return {"Command": {"CommandId": "test-command"}}

        def get_command_invocation(self, **kwargs):
            return {"Status": "Success"}

    assert (
        verify_runtime(SSM(), "i-local-test", sleep=lambda _: None)["status"]
        == "vm_bootstrap_and_containers_verified"
    )


def test_failed_bootstrap_is_a_failure_not_a_ready_vm():
    class SSM:
        def send_command(self, **kwargs):
            return {"Command": {"CommandId": "test-command"}}

        def get_command_invocation(self, **kwargs):
            return {"Status": "Failed"}

    with pytest.raises(RuntimeError):
        verify_runtime(SSM(), "i-local-test", sleep=lambda _: None)
