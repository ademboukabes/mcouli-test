"""merge_heads

Revision ID: 5b6615c9ab1d
Revises: 9f1c3c6e9c1a, c3b8d0f1e2a4
Create Date: 2026-03-20 02:33:56.591359

"""
from typing import Sequence, Union



# revision identifiers, used by Alembic.
revision: str = '5b6615c9ab1d'
down_revision: Union[str, Sequence[str], None] = ('9f1c3c6e9c1a', 'c3b8d0f1e2a4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
