from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.retrieval.milvus_store import initialize_milvus


logger = get_logger("scripts.init_milvus")


async def main() -> None:
    logger.info("scripts.init_milvus.start")
    await initialize_milvus()
    logger.info("scripts.init_milvus.done")


if __name__ == "__main__":
    asyncio.run(main())
