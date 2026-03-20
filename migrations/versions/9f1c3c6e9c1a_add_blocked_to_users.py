"""add-blocked-to-users

Revision ID: 9f1c3c6e9c1a
Revises: 5ead72a95638
Create Date: 2026-03-20 12:50:00.000000

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


# revision identifiers, used by Alembic.
revision: str = "9f1c3c6e9c1a"
down_revision: Union[str, Sequence[str], None] = "5ead72a95638"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("add-blocked-to-users")


def downgrade() -> None:
    run_sql_down("add-blocked-to-users")
