"""add_staff_upload_review_base

Revision ID: c3b8d0f1e2a4
Revises: 5ead72a95638
Create Date: 2026-03-19 12:00:00.000000

"""

from typing import Sequence, Union

from migrations.helper import run_sql_down, run_sql_up


revision: str = "c3b8d0f1e2a4"
down_revision: Union[str, Sequence[str], None] = "5ead72a95638"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    run_sql_up("add-staff-upload-review-base")


def downgrade() -> None:
    run_sql_down("add-staff-upload-review-base")
