from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UploadPhotoInput:
    drive_file_id: str
    taken_at: datetime | None
    day_number: int | None
    visibility: str
