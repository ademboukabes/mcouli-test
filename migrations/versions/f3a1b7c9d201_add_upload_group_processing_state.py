"""add_upload_group_processing_state

Revision ID: f3a1b7c9d201
Revises: df24672cf9f3
Create Date: 2026-04-01 20:40:00.000000

"""

from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


revision: str = "f3a1b7c9d201"
down_revision: Union[str, Sequence[str], None] = "df24672cf9f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("add_upload_group_processing_state")


def downgrade() -> None:
    run_sql_down("add_upload_group_processing_state")
