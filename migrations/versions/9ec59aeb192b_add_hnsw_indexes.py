"""add hnsw indexes

Revision ID: 9ec59aeb192b
Revises: 46bceaf84bd8
Create Date: 2026-08-05 17:25:20.815182

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9ec59aeb192b'
down_revision: Union[str, Sequence[str], None] = '46bceaf84bd8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_face_embedding ON users USING hnsw (face_embedding vector_cosine_ops);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_photo_faces_embedding ON photo_faces USING hnsw (embedding vector_cosine_ops);")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS idx_photo_faces_embedding;")
    op.execute("DROP INDEX IF EXISTS idx_users_face_embedding;")
