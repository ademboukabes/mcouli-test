"""add_audit_photo_event_types

Revision ID: df24672cf9f3
Revises: 2d930ce4c68f
Create Date: 2026-04-01 15:48:51.952542

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


# revision identifiers, used by Alembic.
revision: str = 'df24672cf9f3'
down_revision: Union[str, Sequence[str], None] = '2d930ce4c68f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("add_audit_photo_event_types")


def downgrade() -> None:
    run_sql_down("add_audit_photo_event_types")
