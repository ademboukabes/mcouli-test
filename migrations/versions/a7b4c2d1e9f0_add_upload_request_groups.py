"""add_upload_request_groups

Revision ID: a7b4c2d1e9f0
Revises: c3b8d0f1e2a4
Create Date: 2026-03-25 00:10:00.000000

"""

from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


revision: str = "a7b4c2d1e9f0"
down_revision: Union[str, Sequence[str], None] = "c3b8d0f1e2a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("add-upload-request-groups")


def downgrade() -> None:
    run_sql_down("add-upload-request-groups")
