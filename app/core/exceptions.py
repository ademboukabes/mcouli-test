from abc import ABC, abstractmethod

from fastapi import HTTPException
from app.core.logger import logger
from sqlalchemy.exc import IntegrityError


class AppException:
    @staticmethod
    def not_found(detail: str = "Resource not found") -> HTTPException:
        return HTTPException(status_code=404, detail=detail)

    @staticmethod
    def unauthorized(detail: str = "Unauthorized") -> HTTPException:
        return HTTPException(status_code=401, detail=detail)

    @staticmethod
    def forbidden(detail: str = "Forbidden") -> HTTPException:
        return HTTPException(status_code=403, detail=detail)

    @staticmethod
    def bad_request(detail: str = "Bad request") -> HTTPException:
        return HTTPException(status_code=400, detail=detail)

    @staticmethod
    def payement_required(detail:str = "payement required")->HTTPException:
        return HTTPException(status_code=402,detail=detail)

    @staticmethod
    def internal_error(detail: str = "Internal server error") -> HTTPException:
        return HTTPException(status_code=500, detail=detail)

    @staticmethod
    def conflict(detail: str = "Conflict") -> HTTPException:
        return HTTPException(status_code=409, detail=detail)

    @staticmethod
    def too_many_requests(
        detail: str = "Too many requests. Please try again later.",
        retry_after: int | None = None,
    ) -> HTTPException:
        headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
        return HTTPException(status_code=429, detail=detail, headers=headers)

    @staticmethod
    def storage_error(detail: str = "Storage operation failed") -> HTTPException:
        return HTTPException(status_code=500, detail=detail)

    @staticmethod
    def queue_error(detail: str = "Queue operation failed") -> HTTPException:
        return HTTPException(status_code=500, detail=detail)

    @staticmethod
    def image_quality_error(detail: str = "Image does not meet quality requirements") -> HTTPException:
        return HTTPException(status_code=400, detail=detail)

    @staticmethod
    def image_format_error(detail: str = "Unsupported image format") -> HTTPException:
        return HTTPException(status_code=400, detail=detail)

class DBException(ABC):
    """Abstract class to enforce DB error handling."""

    @staticmethod
    @abstractmethod
    def handle_unique_violation(exc: Exception) -> HTTPException:
        """Handle unique constraint violation."""
        pass

    @staticmethod
    @abstractmethod
    def handle_foreign_key_violation(exc: Exception) -> HTTPException:
        """Handle foreign key constraint violation."""
        pass

    @staticmethod
    @abstractmethod
    def handle_check_violation(exc: Exception) -> HTTPException:
        """Handle check constraint violation."""
        pass

    @staticmethod
    def handle(exc: Exception) -> HTTPException:
        logger.error("Database error: %s", exc)

        if isinstance(exc, HTTPException):
            return exc

        if isinstance(exc, IntegrityError):
            orig = getattr(exc, "orig", None)
            sqlstate = getattr(orig, "sqlstate", None)

            if sqlstate == "23505":
                logger.error("Unique violation detected")
                return DBExceptionImpl.handle_unique_violation(exc)

            if sqlstate == "23503":
                logger.error("Foreign key violation detected")
                return DBExceptionImpl.handle_foreign_key_violation(exc)

            if sqlstate == "23514":
                logger.error("Check violation detected")
                return DBExceptionImpl.handle_check_violation(exc)

        logger.error("Internal server error: %s", exc)
        return HTTPException(status_code=500, detail="Internal server error")


class DBExceptionImpl(DBException):
    """Concrete implementation for asyncpg + SQLAlchemy."""

    @staticmethod
    def handle_unique_violation(exc: Exception) -> HTTPException:
        constraint = getattr(exc, "constraint_name", None)
        err_msg = str(exc).lower()
        if constraint == "staff_users_email_key" or "staff_users_email_key" in err_msg:
            return HTTPException(
                status_code=409,
                detail="Staff user with this email already exists"
            )
        if constraint in ("users_email_key", "idx_users_email") or "idx_users_email" in err_msg or "users_email_key" in err_msg:
            return HTTPException(
                status_code=409,
                detail="Email already in use; please login instead"
            )
        return HTTPException(status_code=409, detail="Resource already exists")

    @staticmethod
    def handle_foreign_key_violation(exc: Exception) -> HTTPException:
        return HTTPException(
            status_code=400, detail="Invalid reference to related resource"
        )

    @staticmethod
    def handle_check_violation(exc: Exception) -> HTTPException:
        return HTTPException(
            status_code=400, detail="Constraint check failed"
        )
