"""create_user_faces

Revision ID: f12ab34cd560
Revises: 4c6c265d0d15
Create Date: 2026-03-15 00:00:00.000000

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up

# revision identifiers, used by Alembic.
revision: str = "f12ab34cd560"
down_revision: Union[str, Sequence[str], None] = "4c6c265d0d15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("create_user_faces")


def downgrade() -> None:
    run_sql_down("create_user_faces")
