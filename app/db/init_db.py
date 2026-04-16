from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import get_logger
from app.db.base import Base
from app.db.models import AuditLog, Document, GraphCheckpoint, KnowledgeBase, Message, Session, User  # noqa: F401
from app.db.session import get_engine, ping_database


logger = get_logger("app.db")


async def initialize_database() -> None:
    await ping_database()
    try:
        async with get_engine().begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    except SQLAlchemyError:
        logger.exception("database.initialize_failed", extra={"log_type": "error"})
        raise
    logger.info("database.initialized")
