"""add_direct_upload_support

Revision ID: 5425a051d68c
Revises: afb0a93aa21e
Create Date: 2026-08-25 02:35:19.168255

"""
from typing import Sequence, Union

from migrations.helper import run_sql_up, run_sql_down


# revision identifiers, used by Alembic.
revision: str = '5425a051d68c'
down_revision: Union[str, Sequence[str], None] = 'afb0a93aa21e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("add_direct_upload_support")


def downgrade() -> None:
    run_sql_down("add_direct_upload_support")
