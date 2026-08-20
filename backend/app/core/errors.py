from typing import Any


class AppError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppError):
    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(
            "RESOURCE_NOT_FOUND",
            f"{resource} 不存在。",
            status_code=404,
            details={"resource": resource, "resourceId": resource_id},
        )


class ConflictError(AppError):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(error_code, message, status_code=409)
