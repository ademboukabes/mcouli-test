from abc import ABC, abstractmethod

from fastapi import HTTPException
import psycopg


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


class DBException(ABC):
    """Abstract class to enforce DB error handling."""

    @staticmethod
    @abstractmethod
    def handle_unique_violation(exc: psycopg.errors.UniqueViolation) -> HTTPException:
        """Handle unique constraint violation."""
        pass

    @staticmethod
    @abstractmethod
    def handle_foreign_key_violation(
        exc: psycopg.errors.ForeignKeyViolation,
    ) -> HTTPException:
        """Handle foreign key constraint violation."""
        pass

    @staticmethod
    @abstractmethod
    def handle_check_violation(exc: psycopg.errors.CheckViolation) -> HTTPException:
        """Handle check constraint violation."""
        pass

    @staticmethod
    def handle(exc: Exception) -> HTTPException:
        if isinstance(exc, psycopg.errors.UniqueViolation):
            return DBExceptionImpl.handle_unique_violation(exc)
        if isinstance(exc, psycopg.errors.ForeignKeyViolation):
            return DBExceptionImpl.handle_foreign_key_violation(exc)
        if isinstance(exc, psycopg.errors.CheckViolation):
            return DBExceptionImpl.handle_check_violation(exc)
        return HTTPException(status_code=500, detail="Internal server error")


class DBExceptionImpl(DBException):
    @staticmethod
    def handle_unique_violation(exc: psycopg.errors.UniqueViolation) -> HTTPException:
        return HTTPException(status_code=409, detail="Resource already exists")

    @staticmethod
    def handle_foreign_key_violation(
        exc: psycopg.errors.ForeignKeyViolation,
    ) -> HTTPException:
        return HTTPException(
            status_code=400, detail="Invalid reference to related resource"
        )

    @staticmethod
    def handle_check_violation(exc: psycopg.errors.CheckViolation) -> HTTPException:
        return HTTPException(status_code=400, detail="Constraint check failed")
