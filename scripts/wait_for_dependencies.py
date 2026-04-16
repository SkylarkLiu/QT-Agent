from __future__ import annotations

import socket
import time

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger


def _probe(host: str, port: int, timeout: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def main() -> None:
    settings = get_settings()
    configure_logging(settings.app.log_level)
    retry = settings.startup_retry
    logger = get_logger("startup.retry")

    if not retry.enabled:
        logger.info("startup_retry.disabled")
        return

    services = [
        ("postgres", settings.db.host, settings.db.port),
        ("redis", settings.redis.host, settings.redis.port),
        ("milvus", settings.milvus.host, settings.milvus.port),
        ("minio", settings.minio.endpoint.split(":")[0], int(settings.minio.endpoint.split(":")[1])),
    ]

    for name, host, port in services:
        for attempt in range(1, retry.max_attempts + 1):
            if _probe(host, port, retry.timeout_seconds):
                logger.info(
                    "startup_retry.service_ready",
                    extra={"service_name": name, "service_host": host, "service_port": port, "attempt": attempt},
                )
                break

            logger.warning(
                "startup_retry.service_waiting",
                extra={"service_name": name, "service_host": host, "service_port": port, "attempt": attempt},
            )
            time.sleep(retry.interval_seconds)
        else:
            raise RuntimeError(f"Dependency {name} is not reachable after {retry.max_attempts} attempts.")


if __name__ == "__main__":
    main()
