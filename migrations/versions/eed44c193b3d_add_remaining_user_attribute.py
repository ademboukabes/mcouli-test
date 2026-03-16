"""add_remaining_user_attribute

Revision ID: eed44c193b3d
Revises: b2e532644368
Create Date: 2026-03-16 01:17:18.583637

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up




# revision identifiers, used by Alembic.
revision: str = 'eed44c193b3d'
down_revision: Union[str, Sequence[str], None] = 'b2e532644368'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("add_remaining_user_attribute")


def downgrade() -> None:
    run_sql_down("add_remaining_user_attribute")
