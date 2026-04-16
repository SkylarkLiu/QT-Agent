"""PostgreSQL Checkpointer — 基于 LangGraph checkpointer 接口的自定义实现。

使用项目已有的 GraphCheckpoint 表（而非 LangGraph 内置的 AsyncPostgresSaver），
避免引入额外的 psycopg 依赖。

职责：
  - 按线程 (thread_id = session_id) 保存图状态
  - 按线程恢复最近的图状态
  - 支持 checkpoint_id 链追溯
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, AsyncIterator
from uuid import uuid4

from langgraph.checkpoints.base import BaseCheckpointSaver
from langgraph.checkpoint.base import Checkpoint as LGCheckpoint
from langgraph.checkpoint.base import CheckpointMetadata as LGCheckpointMetadata
from langgraph.serde.jsonplus import JsonPlusSerializer

from app.core.logging import get_logger

logger = get_logger("app.memory.checkpointer")


class PostgresCheckpointer(BaseCheckpointSaver):
    """基于现有 GraphCheckpoint 表的 LangGraph checkpointer。

    使用方式：
        checkpointer = PostgresCheckpointer(session_factory)
        graph = builder.compile(checkpointer=checkpointer)
        result = await graph.ainvoke(input, config={"configurable": {"thread_id": "session_xxx"}})
    """

    def __init__(self, session_factory) -> None:
        """初始化 checkpointer。

        Args:
            session_factory: 可调用对象，返回 async context manager (AsyncSession)
        """
        super().__init__(serde=JsonPlusSerializer())
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # LangGraph checkpointer 接口实现
    # ------------------------------------------------------------------

    async def setup(self) -> None:
        """初始化 checkpointer（LangGraph 调用）。表已由 app.db.init_db 创建。"""
        pass

    async def aput(
        self,
        config: dict[str, Any],
        checkpoint: LGCheckpoint,
        metadata: LGCheckpointMetadata | None = None,
        new_versions: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """保存 checkpoint 到 PostgreSQL。"""
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        checkpoint_ns = config.get("configurable", {}).get("checkpoint_ns", "")
        checkpoint_id = checkpoint.get("id", str(uuid4()))

        # 将 checkpoint 序列化为 JSON
        checkpoint_data = self.serde.dumpsTyped(checkpoint).model_dump()

        # 元数据
        meta_dict = {}
        if metadata:
            meta_dict.update(
                {
                    "source": metadata.get("source", ""),
                    "step": metadata.get("step", 0),
                    "writes": json.dumps(metadata.get("writes", {}), ensure_ascii=False) if metadata.get("writes") else "",
                }
            )

        async with self._session_factory() as session:
            from app.repositories.chat import GraphCheckpointRepository

            repo = GraphCheckpointRepository(session)
            parent_id = checkpoint.get("parent_checkpoint_id")

            await repo.create(
                session_id=thread_id,
                checkpoint_ns=checkpoint_ns,
                checkpoint_id=checkpoint_id,
                parent_checkpoint_id=parent_id,
                state=checkpoint_data,
                metadata=meta_dict,
            )
            await session.commit()

        logger.debug(
            "checkpointer.put",
            extra={
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
                "step": meta_dict.get("step"),
            },
        )

        return {
            "checkpoint_id": checkpoint_id,
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
        }

    async def aget_tuple(self, config: dict[str, Any]) -> dict[str, Any] | None:
        """获取最新的 checkpoint tuple。"""
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        checkpoint_ns = config.get("configurable", {}).get("checkpoint_ns", "")

        async with self._session_factory() as session:
            from sqlalchemy import select, text
            from app.db.models import GraphCheckpoint

            stmt = (
                select(GraphCheckpoint)
                .where(
                    GraphCheckpoint.session_id == thread_id,
                    GraphCheckpoint.checkpoint_ns == checkpoint_ns,
                )
                .order_by(GraphCheckpoint.created_at.desc())
                .limit(1)
            )
            result = await session.scalar(stmt)
            if result is None:
                return None

            # 反序列化 checkpoint
            try:
                checkpoint = self.serde.loadsTyped(result.state)
            except Exception:
                logger.warning(
                    "checkpointer.deserialize_failed",
                    extra={"checkpoint_id": result.checkpoint_id},
                )
                return None

            # 构建 metadata
            lg_metadata = LGCheckpointMetadata(
                source=result.metadata_.get("source", "loop"),
                step=result.metadata_.get("step", 0),
                writes=json.loads(result.metadata_.get("writes", "{}")) if result.metadata_.get("writes") else {},
            )

            # 构建 pending_writes（空）
            pending_writes: list[tuple[str, str, Any]] = []

            return {
                "config": {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": result.checkpoint_id,
                    }
                },
                "checkpoint": checkpoint,
                "metadata": lg_metadata,
                "pending_writes": pending_writes,
                "parent_config": None,
            }

    async def alist(
        self,
        config: dict[str, Any],
        *,
        filter: dict[str, Any] | None = None,
        before: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """列出 checkpoint 历史。"""
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        checkpoint_ns = config.get("configurable", {}).get("checkpoint_ns", "")

        async with self._session_factory() as session:
            from sqlalchemy import select
            from app.db.models import GraphCheckpoint

            stmt = (
                select(GraphCheckpoint)
                .where(
                    GraphCheckpoint.session_id == thread_id,
                    GraphCheckpoint.checkpoint_ns == checkpoint_ns,
                )
                .order_by(GraphCheckpoint.created_at.desc())
            )
            if limit:
                stmt = stmt.limit(limit)

            result = await session.scalars(stmt)
            for row in result.all():
                try:
                    checkpoint = self.serde.loadsTyped(row.state)
                except Exception:
                    continue

                lg_metadata = LGCheckpointMetadata(
                    source=row.metadata_.get("source", "loop"),
                    step=row.metadata_.get("step", 0),
                    writes=json.loads(row.metadata_.get("writes", "{}")) if row.metadata_.get("writes") else {},
                )

                yield {
                    "config": {
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": row.checkpoint_id,
                        }
                    },
                    "checkpoint": checkpoint,
                    "metadata": lg_metadata,
                    "parent_config": {
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": row.parent_checkpoint_id,
                        }
                    }
                    if row.parent_checkpoint_id
                    else None,
                }
