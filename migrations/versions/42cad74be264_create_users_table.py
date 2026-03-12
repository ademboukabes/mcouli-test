"""create-users-table

Revision ID: 42cad74be264
Revises: e171e4e2247d
Create Date: 2026-03-02 12:22:06.985453

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up




# revision identifiers, used by Alembic.
revision: str = '42cad74be264'
down_revision: Union[str, Sequence[str], None] = 'e171e4e2247d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("create-users-table")


def downgrade() -> None:
    run_sql_down("create-users-table")

