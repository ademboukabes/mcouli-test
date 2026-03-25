"""merge heads

Revision ID: 4dd6658b9f83
Revises: 9f6c1b4a3d21, c3b8d0f1e2a4
Create Date: 2026-03-21 23:29:09.967007

"""
from typing import Sequence, Union



# revision identifiers, used by Alembic.
revision: str = '4dd6658b9f83'
down_revision: Union[str, Sequence[str], None] = ('9f6c1b4a3d21', 'c3b8d0f1e2a4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
