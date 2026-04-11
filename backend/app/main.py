from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.commands import router as commands_router
from app.api.health import router as health_router
from app.api.outcomes import router as outcomes_router
from app.api.sessions import router as sessions_router
from app.core.lifecycle import init_database_file
from app.core.static_files import frontend_dist_dir
from app.domain.errors import NotFoundError, ValidationError


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # FastAPI's `on_event` startup/shutdown hooks are deprecated.
    # v1 uses a minimal lifespan handler instead.
    init_database_file()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Command Deck", version="v1", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def _request_validation_handler(
        _: Request, __: RequestValidationError
    ) -> JSONResponse:
        # FastAPI would normally return 422; v1 API uses 400 with a simple error shape.
        return JSONResponse(status_code=400, content={"error": "Invalid request"})

    @app.exception_handler(ValidationError)
    async def _validation_error_handler(
        _: Request, exc: ValidationError
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    @app.exception_handler(NotFoundError)
    async def _not_found_error_handler(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": str(exc)})

    app.include_router(health_router)
    app.include_router(commands_router)
    app.include_router(outcomes_router)
    app.include_router(sessions_router)

    dist_dir = frontend_dist_dir()
    index_html = dist_dir / "index.html"
    if index_html.is_file():
        # Serve built frontend assets.
        assets_dir = dist_dir / "assets"
        if assets_dir.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=str(assets_dir)),
                name="assets",
            )

        @app.get("/")
        def _index() -> FileResponse:
            return FileResponse(str(index_html))

        # SPA fallback: let the frontend handle client-side routes.
        @app.get("/{path:path}")
        def _spa_fallback(path: str) -> FileResponse:  # noqa: ARG001
            return FileResponse(str(index_html))

    return app


app = create_app()
