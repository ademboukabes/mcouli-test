from fastapi import  UploadFile
from passlib.context import CryptContext
from app.core.exceptions import AppException


class PasswordsUtils:
    pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def check_extension(
    file: UploadFile, ext_content_type_map: dict[str, list[str]]
) -> str:

    allowed_extensions = list(ext_content_type_map.keys())
    if file.filename is None:
        AppException.bad_request("File should have a filename")

    filename_splitted = file.filename.split(".") # type: ignore

    if len(filename_splitted) < 2:
        AppException.bad_request("File should have an extension")


    file_ext = filename_splitted[-1]

    if file_ext not in allowed_extensions:
        AppException.bad_request(f"File extension {file_ext} is not allowed. Allowed extensions are: {', '.join(allowed_extensions)}")


    if file.content_type not in ext_content_type_map[file_ext]:
        AppException.bad_request(f"File content type {file.content_type} does not match extension {file_ext}")


    return file_ext
