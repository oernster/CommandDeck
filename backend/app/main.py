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
from app.version import VERSION


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # FastAPI's `on_event` startup/shutdown hooks are deprecated.
    # v1 uses a minimal lifespan handler instead.
    init_database_file()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Command Deck", version=VERSION, lifespan=lifespan)

    no_store_headers = {
        # Ensure the browser always revalidates API + HTML so updates and data
        # changes are reflected without hard refresh.
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "Expires": "0",
    }

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

    @app.middleware("http")
    async def _cache_control(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path

        if path.startswith("/assets/") and response.status_code == 200:
            # Vite uses content-hashed filenames under /assets, so we can cache
            # these aggressively.
            response.headers.setdefault(
                "Cache-Control",
                "public, max-age=31536000, immutable",
            )
            return response

        if path.startswith("/api/"):
            # Never cache API responses; avoids browsers serving stale data.
            for k, v in no_store_headers.items():
                response.headers.setdefault(k, v)
            return response

        # HTML routes (/, SPA fallback) should not be cached so they always pick
        # up the latest asset hashes.
        content_type = response.headers.get("content-type", "")
        if response.status_code == 200 and content_type.startswith("text/html"):
            for k, v in no_store_headers.items():
                response.headers.setdefault(k, v)
        return response

    dist_dir = frontend_dist_dir()
    index_html = dist_dir / "index.html"
    if index_html.is_file():
        # Serve built frontend assets.
        assets_dir = dist_dir / "assets"
        if assets_dir.is_dir():
            app.mount(
                "/assets",
                StaticFiles(
                    directory=str(assets_dir),
                    html=False,
                    check_dir=True,
                ),
                name="assets",
            )

        @app.get("/")
        def _index() -> FileResponse:
            return FileResponse(str(index_html), headers=no_store_headers)

        # SPA fallback: let the frontend handle client-side routes.
        @app.get("/{path:path}")
        def _spa_fallback(path: str) -> FileResponse:  # noqa: ARG001
            return FileResponse(str(index_html), headers=no_store_headers)

    return app


app = create_app()
