"""create-photos-table

Revision ID: 0952572fe9b4
Revises: 36c3d68f547f
Create Date: 2026-03-12 18:06:18.603970

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


# revision identifiers, used by Alembic.
revision: str = '0952572fe9b4'
down_revision: Union[str, Sequence[str], None] = '36c3d68f547f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("create-photos-table")


def downgrade() -> None:
    run_sql_down("create-photos-table")
