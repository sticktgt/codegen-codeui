from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

LOGGER = logging.getLogger(__name__)


class ApiErrorPayload(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApiError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    LOGGER.warning(
        "API error: method=%s path=%s code=%s status=%s message=%s details=%s",
        request.method,
        request.url.path,
        exc.code,
        exc.status_code,
        exc.message,
        exc.details,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": ApiErrorPayload(code=exc.code, message=exc.message, details=exc.details).model_dump()},
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    LOGGER.exception("Unhandled API error: method=%s path=%s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": ApiErrorPayload(
                code="INTERNAL_ERROR",
                message="Unexpected server error",
                details={"exception": exc.__class__.__name__},
            ).model_dump()
        },
    )
