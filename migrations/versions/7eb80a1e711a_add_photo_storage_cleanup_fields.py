"""add_photo_storage_cleanup_fields

Revision ID: 7eb80a1e711a
Revises: af58506b53a9
Create Date: 2026-08-25 03:15:07.646415

"""
from typing import Sequence, Union

from migrations.helper import run_sql_up, run_sql_down


# revision identifiers, used by Alembic.
revision: str = '7eb80a1e711a'
down_revision: Union[str, Sequence[str], None] = 'af58506b53a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("add_photo_storage_cleanup_fields")


def downgrade() -> None:
    run_sql_down("add_photo_storage_cleanup_fields")
