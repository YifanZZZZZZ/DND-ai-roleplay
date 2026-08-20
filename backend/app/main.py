from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.router import api_router
from backend.app.core.config import get_settings
from backend.app.core.errors import AppError
from backend.app.runtime import get_runtime_supervisor


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    del app
    get_settings().ensure_data_directories()
    await get_runtime_supervisor().recover_interrupted_runs()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
settings.ensure_data_directories()
app.mount("/uploads", StaticFiles(directory=str(settings.data_dir / "uploads")), name="uploads")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_prefix)


@app.exception_handler(AppError)
async def handle_app_error(request: Request, error: AppError) -> JSONResponse:
    del request
    content: dict[str, Any] = {
        "errorCode": error.error_code,
        "message": error.message,
        "details": error.details,
    }
    return JSONResponse(status_code=error.status_code, content=content)
