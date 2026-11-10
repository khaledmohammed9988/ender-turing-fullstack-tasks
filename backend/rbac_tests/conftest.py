from collections.abc import Generator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from app import crud
from app.api.deps import get_db
from app.authorization import Role
from app.core.db import engine
from app.core.security import create_access_token
from app.main import app
from app.models import UserCreate


@pytest.fixture
def setup() -> Generator:
    SQLModel.metadata.create_all(engine)
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(
            bind=connection, join_transaction_mode="create_savepoint"
        ) as session:
            users = {
                role: crud.create_user(
                    session=session,
                    user_create=UserCreate(
                        email=f"rbac-{role.value}@example.com",
                        password="Review-only-Password-123!",
                        role=role,
                    ),
                )
                for role in Role
            }
            headers = {
                role: {
                    "Authorization": "Bearer "
                    + create_access_token(str(user.id), timedelta(minutes=5))
                }
                for role, user in users.items()
            }
            app.dependency_overrides[get_db] = lambda: session
            try:
                with TestClient(app) as client:
                    yield client, session, users, headers
            finally:
                app.dependency_overrides.clear()
                transaction.rollback()
