"""merge_all_heads

Revision ID: 2d930ce4c68f
Revises: 4dd6658b9f83, 5b6615c9ab1d, a1f1d0b6e553, a7b4c2d1e9f0, d2c3e1f4a5b6
Create Date: 2026-04-01 00:01:43.209988

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2d930ce4c68f'
down_revision: Union[str, Sequence[str], None] = ('4dd6658b9f83', '5b6615c9ab1d', 'a1f1d0b6e553', 'a7b4c2d1e9f0', 'd2c3e1f4a5b6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
