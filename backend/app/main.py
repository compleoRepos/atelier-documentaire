from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import create_router
from .core.db import init_db, make_engine, make_session_factory
from .core.observability import Metrics, RequestTelemetry, add_metrics_routes
from .core.settings import get_settings
from .infrastructure.storage import make_storage


def create_app() -> FastAPI:
    settings = get_settings()
    settings.ensure_directories()
    engine = make_engine(settings)
    init_db(engine, settings)
    factory = make_session_factory(engine)
    storage = make_storage(settings)

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()

    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = factory
    app.state.storage = storage
    app.state.metrics = Metrics()
    app.add_middleware(RequestTelemetry)
    add_metrics_routes(app)
    if settings.origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.origins,
            allow_credentials=settings.auth_mode != "bearer",
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
        )
    app.include_router(create_router(factory, storage, settings))
    if settings.rag_mode != "DISABLED" or settings.rag_admin_enabled:
        # DICE (RAG) : rien n'est importé ni monté en DISABLED sans administration.
        from .rag.api.mount import mount_rag

        mount_rag(app, factory, engine, settings)

    @app.get("/health")
    def root_health():
        return {"status": "ok", "service": "translator"}

    if settings.frontend_dir and Path(settings.frontend_dir).is_dir():
        frontend = Path(settings.frontend_dir)
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets") if (
            frontend / "assets"
        ).is_dir() else None

        @app.get("/{path:path}")
        def frontend_fallback(path: str):
            if path.startswith("api/"):
                return {"detail": "Not found"}
            candidate = (frontend / path).resolve()
            if frontend.resolve() in candidate.parents and candidate.is_file():
                return FileResponse(candidate)
            index = frontend / "index.html"
            return FileResponse(index) if index.exists() else {"detail": "Not found"}

    return app


app = create_app()
