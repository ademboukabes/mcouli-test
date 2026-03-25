"""alter photo_faces embedding dimension to 512

Revision ID: 9f6c1b4a3d21
Revises: 5ead72a95638
Create Date: 2026-03-21 23:23:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9f6c1b4a3d21"
down_revision: Union[str, Sequence[str], None] = "5ead72a95638"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE photo_faces ALTER COLUMN embedding TYPE vector(512);")


def downgrade() -> None:
    op.execute("ALTER TABLE photo_faces ALTER COLUMN embedding TYPE vector(1536);")
