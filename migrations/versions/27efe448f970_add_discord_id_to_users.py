"""add_discord_id_to_users

Revision ID: 27efe448f970
Revises: 7eb80a1e711a
Create Date: 2026-10-06 23:57:24.958872

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from migrations.helper import run_sql_up, run_sql_down


# revision identifiers, used by Alembic.
revision: str = '27efe448f970'
down_revision: Union[str, Sequence[str], None] = '7eb80a1e711a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("add_discord_id_to_users")


def downgrade() -> None:
    run_sql_down("add_discord_id_to_users")
