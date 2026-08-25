"""add_end_date_to_events

Revision ID: afb0a93aa21e
Revises: 9ec59aeb192b
Create Date: 2026-08-25 01:34:59.327934

"""
from typing import Sequence, Union

from migrations.helper import run_sql_up, run_sql_down


# revision identifiers, used by Alembic.
revision: str = 'afb0a93aa21e'
down_revision: Union[str, Sequence[str], None] = '9ec59aeb192b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    run_sql_up("add_end_date_to_events")


def downgrade() -> None:
    """Downgrade schema."""
    run_sql_down("add_end_date_to_events")
