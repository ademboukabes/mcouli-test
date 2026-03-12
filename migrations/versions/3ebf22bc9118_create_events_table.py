"""create-events-table

Revision ID: 3ebf22bc9118
Revises: 4c6c265d0d15
Create Date: 2026-03-12 18:05:08.081468

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


# revision identifiers, used by Alembic.
revision: str = '3ebf22bc9118'
down_revision: Union[str, Sequence[str], None] = '4c6c265d0d15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("create-events-table")


def downgrade() -> None:
    run_sql_down("create-events-table")
