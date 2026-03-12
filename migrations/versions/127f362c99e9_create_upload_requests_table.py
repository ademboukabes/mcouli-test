"""create-upload-requests-table

Revision ID: 127f362c99e9
Revises: 78f200d4cec7
Create Date: 2026-03-12 18:08:53.285973

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


# revision identifiers, used by Alembic.
revision: str = '127f362c99e9'
down_revision: Union[str, Sequence[str], None] = '78f200d4cec7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("create-upload-requests-table")


def downgrade() -> None:
    run_sql_down("create-upload-requests-table")
