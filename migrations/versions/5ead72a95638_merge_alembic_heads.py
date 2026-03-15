"""merge alembic heads

Revision ID: 5ead72a95638
Revises: a4b8c2d9e3f1, b2e532644368
Create Date: 2026-03-15 14:24:04.545981

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = '5ead72a95638'
down_revision: Union[str, Sequence[str], None] = ('a4b8c2d9e3f1', 'b2e532644368')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
