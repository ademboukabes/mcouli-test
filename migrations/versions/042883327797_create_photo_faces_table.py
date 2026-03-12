"""create-photo-faces-table

Revision ID: 042883327797
Revises: b29d627b8e27
Create Date: 2026-03-12 18:07:41.843182

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


# revision identifiers, used by Alembic.
revision: str = '042883327797'
down_revision: Union[str, Sequence[str], None] = 'b29d627b8e27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("create-photo-faces-table")


def downgrade() -> None:
    run_sql_down("create-photo-faces-table")
