"""create-user-photos-table

Revision ID: 5d10bf2ace55
Revises: 0952572fe9b4
Create Date: 2026-03-12 18:06:41.287720

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


# revision identifiers, used by Alembic.
revision: str = '5d10bf2ace55'
down_revision: Union[str, Sequence[str], None] = '0952572fe9b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("create-user-photos-table")


def downgrade() -> None:
    run_sql_down("create-user-photos-table")
