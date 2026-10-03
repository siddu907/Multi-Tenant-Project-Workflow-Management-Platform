from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.core.exceptions import AppError


def register_exception_handlers(app):
    def error_response(status_code: int, message: str, detail=None):
        return {
            "success": False,
            "error": {"code": f"HTTP_{status_code}", "message": message},
            "detail": detail if detail is not None else message,
        }

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content=error_response(exc.status_code, exc.message))

    @app.exception_handler(HTTPException)
    async def handle_http_error(request: Request, exc: HTTPException):
        if exc.status_code == 403:
            message = "Insufficient permissions"
            detail = message
        else:
            message = exc.detail if isinstance(exc.detail, str) else "Request failed"
            detail = exc.detail
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(exc.status_code, message, detail),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        details = []
        for error in exc.errors():
            normalized_error = dict(error)
            if "ctx" in normalized_error:
                normalized_error["ctx"] = {
                    key: str(value) for key, value in normalized_error["ctx"].items()
                }
            details.append(normalized_error)
        return JSONResponse(
            status_code=422,
            content=error_response(422, "Request validation failed", details),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        return JSONResponse(status_code=500, content=error_response(500, "Internal server error"))
