"""replace-staff-discord-with-password

Revision ID: 989510311240
Revises: 8e9b7a6c4d11
Create Date: 2026-03-13 20:11:15.523910

"""
from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up




# revision identifiers, used by Alembic.
revision: str = '989510311240'
down_revision: Union[str, Sequence[str], None] = '8e9b7a6c4d11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("replace-staff-discord-with-password")
    
    
   


def downgrade() -> None:
    run_sql_down("replace-staff-discord-with-password")
