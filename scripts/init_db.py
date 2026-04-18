from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.db.init_db import initialize_database
from app.db.session import close_engine


logger = get_logger("scripts.init_db")


async def main() -> None:
    logger.info("scripts.init_db.start")
    await initialize_database()
    logger.info("scripts.init_db.done")
    await close_engine()


if __name__ == "__main__":
    asyncio.run(main())
