from fastapi import FastAPI

from app.api.v1.routes.health import router as health_router
from app.api.v1.router import router as api_router
from app.core.config import get_settings
from app.core.logging import RequestContextMiddleware, configure_logging
from app.lifecycle import lifespan


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.app.log_level)

    app = FastAPI(
        title=settings.app.name,
        version="0.1.0",
        debug=settings.app.debug,
        lifespan=lifespan,
    )
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.app.api_prefix)

    return app


app = create_app()
