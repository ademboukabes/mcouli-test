"""add_session_idle_absolute_expiry

Revision ID: 46bceaf84bd8
Revises: e49065cb125a
Create Date: 2026-07-27 13:03:49.830264

"""
from typing import Sequence, Union

from migrations.helper import run_sql_up


# revision identifiers, used by Alembic.
revision: str = '46bceaf84bd8'
down_revision: Union[str, Sequence[str], None] = 'e49065cb125a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("add_session_idle_absolute_expiry")
    pass


def downgrade() -> None:
    run_sql_up("add_session_idle_absolute_expiry")
    pass
