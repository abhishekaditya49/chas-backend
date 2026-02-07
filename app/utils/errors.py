"""Custom exception hierarchy for the CHAS API."""

from __future__ import annotations


class AppError(Exception):
    """Base application error with a stable machine-readable code."""

    def __init__(self, message: str, code: str, status_code: int = 400) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)

    def to_dict(self) -> dict[str, str]:
        """Serialize the error in the API standard shape."""
        return {"error": self.message, "code": self.code}


class InsufficientCCError(AppError):
    """Raised when a user tries to spend more CC than they have."""

    def __init__(self, required: int, available: int) -> None:
        super().__init__(
            message=f"Insufficient CC: need {required}, have {available}",
            code="INSUFFICIENT_CC",
        )


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str) -> None:
        super().__init__(message=f"{resource} not found", code="NOT_FOUND", status_code=404)


class ForbiddenError(AppError):
    """Raised when the user lacks permission for the action."""

    def __init__(self, reason: str = "You don't have permission") -> None:
        super().__init__(message=reason, code="FORBIDDEN", status_code=403)


class ConflictError(AppError):
    """Raised on duplicate/conflicting operations."""

    def __init__(self, reason: str, code: str = "CONFLICT") -> None:
        super().__init__(message=reason, code=code, status_code=409)


class UnauthorizedError(AppError):
    """Raised when the caller is not authenticated."""

    def __init__(self, reason: str = "Unauthorized") -> None:
        super().__init__(message=reason, code="UNAUTHORIZED", status_code=401)


class InvalidInputError(AppError):
    """Raised for request payload or parameter validation issues."""

    def __init__(self, reason: str) -> None:
        super().__init__(message=reason, code="INVALID_INPUT", status_code=422)
