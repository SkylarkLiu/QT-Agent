from fastapi import APIRouter

from app.core.config import get_settings


router = APIRouter()


@router.get("/health", summary="Health check")
async def health_check() -> dict[str, object]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app.name,
        "env": settings.app.env,
        "version": "0.1.0",
    }
