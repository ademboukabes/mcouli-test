"""add_device_push_token_fields

Revision ID: d2c3e1f4a5b6
Revises: 5ead72a95638
Create Date: 2026-03-25 00:00:00.000000

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


# revision identifiers, used by Alembic.
revision: str = 'd2c3e1f4a5b6'
down_revision: Union[str, Sequence[str], None] = '5ead72a95638'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("add_device_push_token_fields")


def downgrade() -> None:
    run_sql_down("add_device_push_token_fields")
