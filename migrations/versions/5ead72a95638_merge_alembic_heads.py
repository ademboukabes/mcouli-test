"""merge alembic heads

Revision ID: 5ead72a95638
Revises: eed44c193b3d
Create Date: 2026-03-15 14:24:04.545981

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = '5ead72a95638'
down_revision: Union[str, Sequence[str], None] = 'eed44c193b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
