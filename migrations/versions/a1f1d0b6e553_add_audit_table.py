"""add-audit-table

Revision ID: a1f1d0b6e553
Revises: 5ead72a95638
Create Date: 2026-03-20 00:00:00.000000

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


# revision identifiers, used by Alembic.
revision: str = 'a1f1d0b6e553'
down_revision: Union[str, Sequence[str], None] = '5ead72a95638'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("add-audit-table")


def downgrade() -> None:
    run_sql_down("add-audit-table")
