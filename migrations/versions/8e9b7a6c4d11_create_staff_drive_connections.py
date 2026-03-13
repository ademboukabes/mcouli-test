"""create_staff_drive_connections

Revision ID: 8e9b7a6c4d11
Revises: 127f362c99e9
Create Date: 2026-03-13 03:30:00.000000

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


revision: str = "8e9b7a6c4d11"
down_revision: Union[str, Sequence[str], None] = "127f362c99e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("create-staff-drive-connections")


def downgrade() -> None:
    run_sql_down("create-staff-drive-connections")
