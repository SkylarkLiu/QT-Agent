from fastapi import APIRouter

from app.api.v1.routes.chat import router as chat_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.ingestion import router as ingestion_router


router = APIRouter()
router.include_router(health_router, tags=["health"])
router.include_router(chat_router, tags=["chat"])
router.include_router(ingestion_router, tags=["ingestion", "knowledge"])
