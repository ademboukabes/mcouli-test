"""add_drive_sync_fields_to_photos

Revision ID: af58506b53a9
Revises: 5425a051d68c
Create Date: 2026-08-25 02:58:36.347923

"""
from typing import Sequence, Union

from migrations.helper import run_sql_up, run_sql_down


# revision identifiers, used by Alembic.
revision: str = 'af58506b53a9'
down_revision: Union[str, Sequence[str], None] = '5425a051d68c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("add_drive_sync_fields_to_photos")


def downgrade() -> None:
    run_sql_down("add_drive_sync_fields_to_photos")
