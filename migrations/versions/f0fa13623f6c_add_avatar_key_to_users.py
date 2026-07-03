"""add_avatar_key_to_users

Revision ID: f0fa13623f6c
Revises: f3a1b7c9d201
Create Date: 2026-07-03 01:46:31.410873

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up

# revision identifiers, used by Alembic.
revision: str = 'f0fa13623f6c'
down_revision: Union[str, Sequence[str], None] = 'f3a1b7c9d201'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("add_avatar_key_to_users")


def downgrade() -> None:
    run_sql_down("add_avatar_key_to_users")