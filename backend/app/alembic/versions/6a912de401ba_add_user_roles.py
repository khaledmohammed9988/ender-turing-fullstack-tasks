"""Add canonical user roles and migrate legacy administrators."""
from alembic import op
import sqlalchemy as sa

revision = "6a912de401ba"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user", sa.Column("role", sa.String(16), nullable=False, server_default="member"))
    op.execute("UPDATE \"user\" SET role = 'admin' WHERE is_superuser = true")
    op.create_check_constraint("user_role", "user", "role IN ('admin', 'manager', 'member')")


def downgrade():
    op.execute("UPDATE \"user\" SET is_superuser = (role = 'admin')")
    op.drop_constraint("user_role", "user", type_="check")
    op.drop_column("user", "role")
