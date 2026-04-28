from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from codeui.api import routes_change_requests, routes_health, routes_projects, routes_requirements, routes_runs, routes_sessions, routes_settings, routes_ui_state, routes_workspaces
from codeui.config import load_settings
from codeui.errors import ApiError, api_error_handler, unhandled_error_handler
from codeui.logger import configure_logging, get_logger

settings = load_settings()
configure_logging(settings)
LOGGER = get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app.name, version=settings.app.version)
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(routes_health.router)
    app.include_router(routes_settings.router)
    app.include_router(routes_ui_state.router)
    app.include_router(routes_projects.router)
    app.include_router(routes_requirements.router)
    app.include_router(routes_change_requests.router)
    app.include_router(routes_sessions.router)
    app.include_router(routes_runs.router)
    app.include_router(routes_workspaces.router)

    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    LOGGER.info("codeui app created: codecollector_root=%s runs_root=%s", settings.codecollector_root, settings.runs_root)
    return app


app = create_app()
