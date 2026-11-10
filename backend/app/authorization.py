from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"


class Permission(StrEnum):
    READ_USERS = "users:read"
    MANAGE_USERS = "users:manage"
    READ_METRICS = "metrics:read"


ROLE_PERMISSIONS = {
    Role.ADMIN: frozenset(Permission),
    Role.MANAGER: frozenset({Permission.READ_USERS, Permission.READ_METRICS}),
    Role.MEMBER: frozenset(),
}


def permissions_for(role: Role) -> list[str]:
    return sorted(permission.value for permission in ROLE_PERMISSIONS.get(role, ()))
