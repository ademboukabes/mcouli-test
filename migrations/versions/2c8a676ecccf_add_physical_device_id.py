"""add_physical_device_id

Revision ID: 2c8a676ecccf
Revises: f0fa13623f6c
Create Date: 2026-07-17 02:15:43.587673

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


# revision identifiers, used by Alembic.
revision: str = '2c8a676ecccf'
down_revision: Union[str, Sequence[str], None] = 'f0fa13623f6c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("add_physical_device_id")


def downgrade() -> None:
    run_sql_down("add_physical_device_id")