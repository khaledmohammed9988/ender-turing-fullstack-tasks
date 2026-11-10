import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.authorization import Role
from app.core.config import settings
from app.core.security import ALGORITHM

PREFIX = "/api/v1"


@pytest.mark.parametrize(
    "role,allowed", [(Role.ADMIN, True), (Role.MANAGER, True), (Role.MEMBER, False)]
)
def test_read_permissions_and_safe_responses(setup, role, allowed):
    client, _, _, headers = setup
    for path in ("/users/", "/metrics/"):
        response = client.get(PREFIX + path, headers=headers[role])
        assert response.status_code == (200 if allowed else 403)
        assert "hashed_password" not in response.text
    me = client.get(PREFIX + "/users/me", headers=headers[role]).json()
    assert me["role"] == role.value
    assert ("users:manage" in me["permissions"]) == (role == Role.ADMIN)


@pytest.mark.parametrize("role", list(Role))
def test_user_management_is_admin_only(setup, role):
    client, _, users, headers = setup
    response = client.post(
        PREFIX + "/users/",
        headers=headers[role],
        json={
            "email": f"created-{uuid.uuid4()}@example.com",
            "password": "Review-only-Password-123!",
            "role": "manager",
        },
    )
    assert response.status_code == (200 if role == Role.ADMIN else 403)
    target = users[Role.MEMBER]
    assert client.patch(
        PREFIX + f"/users/{target.id}",
        headers=headers[role],
        json={"full_name": "Changed"},
    ).status_code == (200 if role == Role.ADMIN else 403)
    if role != Role.ADMIN:
        assert (
            client.delete(
                PREFIX + f"/users/{target.id}", headers=headers[role]
            ).status_code
            == 403
        )


@pytest.mark.parametrize("role", list(Role))
def test_profile_update_cannot_escalate(setup, role):
    client, _, _, headers = setup
    response = client.patch(
        PREFIX + "/users/me", headers=headers[role], json={"full_name": "Own name"}
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Own name"
    for field, value in (
        ("role", "admin"),
        ("is_superuser", True),
        ("is_active", True),
    ):
        response = client.patch(
            PREFIX + "/users/me", headers=headers[role], json={field: value}
        )
        assert response.status_code == 422
    assert (
        client.get(PREFIX + "/users/me", headers=headers[role]).json()["role"]
        == role.value
    )


def test_signup_cannot_assign_roles_or_legacy_superuser(setup):
    client, _, _, _ = setup
    for extra in ({"role": "admin"}, {"is_superuser": True}):
        response = client.post(
            PREFIX + "/users/signup",
            json={
                "email": "signup-attempt@example.com",
                "password": "Review-only-Password-123!",
                **extra,
            },
        )
        assert response.status_code == 422
    response = client.post(
        PREFIX + "/users/signup",
        json={
            "email": "signup-ok@example.com",
            "password": "Review-only-Password-123!",
        },
    )
    assert response.status_code == 200
    assert response.json()["role"] == "member"
    assert response.json()["permissions"] == []


def test_role_changes_take_effect_with_existing_token(setup):
    client, _, users, headers = setup
    manager = users[Role.MANAGER]
    assert (
        client.get(PREFIX + "/metrics/", headers=headers[Role.MANAGER]).status_code
        == 200
    )
    changed = client.patch(
        PREFIX + f"/users/{manager.id}",
        headers=headers[Role.ADMIN],
        json={"role": "member"},
    )
    assert changed.status_code == 200
    assert changed.json()["role"] == "member"
    assert (
        client.get(PREFIX + "/metrics/", headers=headers[Role.MANAGER]).status_code
        == 403
    )


def test_tokens_do_not_choose_roles_and_authentication_is_401(setup):
    client, _, users, _ = setup
    for headers in ({}, {"Authorization": "Bearer invalid"}):
        assert client.get(PREFIX + "/users/", headers=headers).status_code == 401
    token = jwt.encode(
        {
            "sub": str(users[Role.MEMBER].id),
            "role": "admin",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )
    assert (
        client.get(
            PREFIX + "/users/", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 403
    )


def test_admin_cannot_remove_own_access_and_invalid_role_is_rejected(setup):
    client, _, users, headers = setup
    path = PREFIX + f"/users/{users[Role.ADMIN].id}"
    for patch in ({"role": "member"}, {"is_active": False}):
        assert (
            client.patch(path, headers=headers[Role.ADMIN], json=patch).status_code
            == 403
        )
    for patch in ({"role": "owner"}, {"is_superuser": True}):
        assert (
            client.patch(path, headers=headers[Role.ADMIN], json=patch).status_code
            == 422
        )


def test_member_cannot_read_another_profile(setup):
    client, _, users, headers = setup
    response = client.get(
        PREFIX + f"/users/{users[Role.ADMIN].id}", headers=headers[Role.MEMBER]
    )
    assert response.status_code == 403
