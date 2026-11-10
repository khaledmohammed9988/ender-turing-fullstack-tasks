"""Explicit development seed; requires a password supplied by the operator."""

import os

from sqlmodel import Session

from app import crud
from app.authorization import Role
from app.core.config import settings
from app.core.db import engine, init_db
from app.models import UserCreate


def main():
    if settings.FASTAPI_ENV != "development":
        raise SystemExit("Demo seed is restricted to FASTAPI_ENV=development")
    password = os.environ.get("RBAC_DEMO_PASSWORD", "")
    if len(password) < 12:
        raise SystemExit("Set RBAC_DEMO_PASSWORD to at least 12 characters")
    with Session(engine) as session:
        init_db(session)
        for role in Role:
            email = f"{role.value}@example.com"
            if not crud.get_user_by_email(session=session, email=email):
                crud.create_user(
                    session=session,
                    user_create=UserCreate(
                        email=email,
                        password=password,
                        role=role,
                        full_name=role.value.title(),
                    ),
                )


if __name__ == "__main__":
    main()
