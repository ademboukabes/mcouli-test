"""create-photo-approvals-table

Revision ID: b29d627b8e27
Revises: 5d10bf2ace55
Create Date: 2026-03-12 18:07:12.715390

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


# revision identifiers, used by Alembic.
revision: str = 'b29d627b8e27'
down_revision: Union[str, Sequence[str], None] = '5d10bf2ace55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("create-photo-approvals-table")


def downgrade() -> None:
    run_sql_down("create-photo-approvals-table")
