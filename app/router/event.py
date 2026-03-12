from fastapi import APIRouter, UploadFile, File


router = APIRouter()


@router.post("/api/v1/events/{event_id}/enroll", status_code=202)
async def enroll_event(
    event_id: str,
    files: list[UploadFile] = File(...)
):
    # Enrollment logic will be implemented in later steps
    return {"detail": "Enrollment started"}
