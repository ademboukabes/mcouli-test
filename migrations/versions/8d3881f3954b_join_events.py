"""join_events

Revision ID: 8d3881f3954b
Revises: afb3aa8bddc7
Create Date: 2026-03-07 13:28:13.139441

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from migrations.helper import run_sql_down, run_sql_up


# revision identifiers, used by Alembic.
revision: str = '8d3881f3954b'
down_revision: Union[str, Sequence[str], None] = 'afb3aa8bddc7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("join_events") 
    pass


def downgrade() -> None:
    run_sql_down("join_events")
    pass
