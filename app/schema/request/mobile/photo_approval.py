from typing import Literal

from pydantic import BaseModel


class PhotoApprovalRequest(BaseModel):
    decision: Literal["approved", "rejected"]
