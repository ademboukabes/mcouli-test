"""staff_sessions

Revision ID: 55ed7d46c7d2
Revises: b2e532644368
Create Date: 2026-03-16 22:16:21.662474

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


# revision identifiers, used by Alembic.
revision: str = '55ed7d46c7d2'
down_revision: Union[str, Sequence[str], None] = 'b2e532644368'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("staff_sessions")


def downgrade() -> None:
    run_sql_down("staff_sessions")
