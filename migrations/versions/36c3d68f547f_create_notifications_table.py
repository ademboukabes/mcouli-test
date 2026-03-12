"""create-notifications-table

Revision ID: 36c3d68f547f
Revises: 4ecce8f0b1bd
Create Date: 2026-03-12 18:05:49.743263

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


# revision identifiers, used by Alembic.
revision: str = '36c3d68f547f'
down_revision: Union[str, Sequence[str], None] = '4ecce8f0b1bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("create-notifications-table")


def downgrade() -> None:
    run_sql_down("create-notifications-table")
