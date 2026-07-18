"""create_refresh_tokens

Revision ID: e49065cb125a
Revises: 2c8a676ecccf
Create Date: 2026-07-17 02:21:18.789969

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


# revision identifiers, used by Alembic.
revision: str = 'e49065cb125a'
down_revision: Union[str, Sequence[str], None] = '2c8a676ecccf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("create_refresh_tokens")


def downgrade() -> None:
    run_sql_down("create_refresh_tokens")
