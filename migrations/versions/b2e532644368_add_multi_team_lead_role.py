"""add_multi_team_lead_role

Revision ID: b2e532644368
Revises: 989510311240
Create Date: 2026-03-13 22:52:31.538256

"""
from typing import Sequence, Union



from migrations.helper import run_sql_down, run_sql_up


# revision identifiers, used by Alembic.
revision: str = 'b2e532644368'
down_revision: Union[str, Sequence[str], None] = '989510311240'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("add_multi_team_lead_role")




def downgrade() -> None:
    run_sql_down("add_multi_team_lead_role")
