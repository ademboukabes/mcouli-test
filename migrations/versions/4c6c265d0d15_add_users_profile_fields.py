"""add-users-profile-fields

Revision ID: 4c6c265d0d15
Revises: b037dbfdbb1f
Create Date: 2026-03-12 18:04:51.055109

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c6c265d0d15'
down_revision: Union[str, Sequence[str], None] = 'b037dbfdbb1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
