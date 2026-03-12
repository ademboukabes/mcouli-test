"""staff_user

Revision ID: 87919323c62e
Revises: 42cad74be264
Create Date: 2026-03-02 12:24:05.234386

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up




# revision identifiers, used by Alembic.
revision: str = '87919323c62e'
down_revision: Union[str, Sequence[str], None] = '42cad74be264'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("create_staff_user")



def downgrade() -> None:
    run_sql_down("create_staff_user")

