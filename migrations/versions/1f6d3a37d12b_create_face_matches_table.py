"""create-face-matches-table

Revision ID: 1f6d3a37d12b
Revises: 042883327797
Create Date: 2026-03-12 18:08:08.162096

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


# revision identifiers, used by Alembic.
revision: str = '1f6d3a37d12b'
down_revision: Union[str, Sequence[str], None] = '042883327797'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("create-face-matches-table")


def downgrade() -> None:
    run_sql_down("create-face-matches-table")
