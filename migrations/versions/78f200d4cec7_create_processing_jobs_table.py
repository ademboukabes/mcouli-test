"""create-processing-jobs-table

Revision ID: 78f200d4cec7
Revises: 1f6d3a37d12b
Create Date: 2026-03-12 18:08:29.516343

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


# revision identifiers, used by Alembic.
revision: str = '78f200d4cec7'
down_revision: Union[str, Sequence[str], None] = '1f6d3a37d12b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("create-processing-jobs-table")


def downgrade() -> None:
    run_sql_down("create-processing-jobs-table")
