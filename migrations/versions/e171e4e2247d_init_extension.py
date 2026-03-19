"""init_extension

Revision ID: e171e4e2247d
Revises:
Create Date: 2026-02-28 13:58:27.732494

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


# revision identifiers, used by Alembic.
revision: str = 'e171e4e2247d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("init_extension")

def downgrade() -> None:
    run_sql_down("init_extension")
