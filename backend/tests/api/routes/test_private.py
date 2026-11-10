from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import User


def test_unauthenticated_development_helper_is_not_exposed(
    client: TestClient, db: Session
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/private/users/",
        json={
            "email": "must-not-exist@example.com",
            "password": "password123",
            "full_name": "Blocked",
        },
    )
    assert response.status_code in {404, 405}
    assert (
        db.exec(select(User).where(User.email == "must-not-exist@example.com")).first()
        is None
    )
