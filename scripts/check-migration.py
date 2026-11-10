"""Destructive migration regression check: use a dedicated EMPTY scratch database only."""

import os
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

# Caller must explicitly provide a distinct scratch URL; never use the application DB.
url = os.environ["MIGRATION_TEST_DATABASE_URL"]
if url == os.environ.get("DATABASE_URL"):
    raise SystemExit("Refusing to use the application database")
os.environ["DATABASE_URL"] = url
engine = create_engine(url)
with engine.connect() as connection:
    assert not connection.execute(
        text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
    ).all(), "Scratch database must be empty"
config = Config("alembic.ini")  # run from backend/
command.upgrade(config, "fe56fa70289e")
ids = [str(uuid.uuid4()), str(uuid.uuid4())]
with engine.begin() as connection:
    for index, user_id in enumerate(ids):
        connection.execute(
            text(
                'INSERT INTO "user" (id,email,is_active,is_superuser,hashed_password) VALUES (:id,:email,true,:admin,:password)'
            ),
            {
                "id": user_id,
                "email": f"migration-{index}@example.com",
                "admin": index == 0,
                "password": "not-a-login-hash",
            },
        )
command.upgrade(config, "head")
with engine.connect() as connection:
    values = dict(connection.execute(text('SELECT email,role FROM "user"')).all())
    assert values == {
        "migration-0@example.com": "admin",
        "migration-1@example.com": "member",
    }
with engine.begin() as connection:
    connection.execute(
        text("UPDATE \"user\" SET role='manager' WHERE email='migration-1@example.com'")
    )
command.downgrade(config, "fe56fa70289e")
with engine.connect() as connection:
    assert dict(
        connection.execute(text('SELECT email,is_superuser FROM "user"')).all()
    ) == {"migration-0@example.com": True, "migration-1@example.com": False}
command.upgrade(config, "head")
print(
    "Migration passed: legacy admin/member backfill; downgrade mirror; re-upgrade. Manager becomes member after a lossy downgrade, as documented."
)
