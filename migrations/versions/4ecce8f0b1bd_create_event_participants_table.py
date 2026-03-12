"""create-event-participants-table

Revision ID: 4ecce8f0b1bd
Revises: 3ebf22bc9118
Create Date: 2026-03-12 18:05:25.382712

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


# revision identifiers, used by Alembic.
revision: str = '4ecce8f0b1bd'
down_revision: Union[str, Sequence[str], None] = '3ebf22bc9118'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("create-event-participants-table")


def downgrade() -> None:
    run_sql_down("create-event-participants-table")
