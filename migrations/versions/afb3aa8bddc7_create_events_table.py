"""create_events_table

Revision ID: afb3aa8bddc7
Revises: b037dbfdbb1f
Create Date: 2026-03-06 21:39:13.185794

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from migrations.helper import run_sql_down, run_sql_up



# revision identifiers, used by Alembic.
revision: str = 'afb3aa8bddc7'
down_revision: Union[str, Sequence[str], None] = 'b037dbfdbb1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("create_events_table") 
    pass


def downgrade() -> None:
    run_sql_down("create_events_table")
    pass
