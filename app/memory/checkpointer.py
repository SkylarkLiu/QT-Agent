"""PostgreSQL Checkpointer — 基于 LangGraph checkpointer 接口的自定义实现。

使用项目已有的 GraphCheckpoint 表（而非 LangGraph 内置的 AsyncPostgresSaver），
避免引入额外的 psycopg 依赖。

职责：
  - 按线程 (thread_id = session_id) 保存图状态
  - 按线程恢复最近的图状态
  - 支持 checkpoint_id 链追溯
  - 支持中间 writes 持久化
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, AsyncIterator, Sequence, cast
from uuid import uuid4

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint as LGCheckpoint,
    CheckpointMetadata as LGCheckpointMetadata,
    CheckpointTuple,
    PendingWrite,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from langchain_core.runnables import RunnableConfig

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
        config: RunnableConfig,
        checkpoint: LGCheckpoint,
        metadata: LGCheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """保存 checkpoint 到 PostgreSQL。"""
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        checkpoint_ns = config.get("configurable", {}).get("checkpoint_ns", "")
        checkpoint_id = checkpoint.get("id", str(uuid4()))

        # 构建存储元数据（保留 source/step/run_id）
        meta_dict = {
            "source": metadata.get("source", "loop"),
            "step": metadata.get("step", 0),
            "run_id": metadata.get("run_id", ""),
            "parents": json.dumps(metadata.get("parents", {}), ensure_ascii=False) if metadata.get("parents") else "",
        }

        # 将 checkpoint 序列化后存入 state 字段（json.loads 桥接 TypedDict → dict）
        checkpoint_data = json.loads(json.dumps(checkpoint, ensure_ascii=False, default=str))

        async with self._session_factory()() as session:
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

        return cast(
            RunnableConfig,
            {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id,
                }
            },
        )

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """保存中间 writes 到 checkpoint 记录的 metadata 中。

        LangGraph 在子图执行过程中会调用此方法来持久化中间状态写入。
        将 writes 序列化后追加到对应 checkpoint 的 metadata.writes 字段。
        """
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        checkpoint_id = config.get("configurable", {}).get("checkpoint_id")

        if not checkpoint_id:
            logger.warning("checkpointer.aput_writes.skip", extra={"thread_id": thread_id, "reason": "no checkpoint_id"})
            return

        serialized_writes = json.dumps(
            [{"channel": ch, "value": val, "task_id": task_id, "task_path": task_path} for ch, val in writes],
            ensure_ascii=False,
            default=str,
        )

        async with self._session_factory()() as session:
            from sqlalchemy import select, update
            from app.db.models import GraphCheckpoint

            stmt = (
                select(GraphCheckpoint)
                .where(
                    GraphCheckpoint.session_id == thread_id,
                    GraphCheckpoint.checkpoint_id == checkpoint_id,
                )
                .limit(1)
            )
            row = await session.scalar(stmt)
            if row is not None:
                meta = dict(row.metadata_) if row.metadata_ else {}
                meta["pending_writes"] = serialized_writes
                row.metadata_ = meta
                await session.commit()

        logger.debug(
            "checkpointer.aput_writes",
            extra={"thread_id": thread_id, "checkpoint_id": checkpoint_id, "task_id": task_id, "write_count": len(writes)},
        )

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """获取最新的 checkpoint tuple。"""
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        checkpoint_ns = config.get("configurable", {}).get("checkpoint_ns", "")

        async with self._session_factory()() as session:
            from sqlalchemy import select
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
                checkpoint = result.state
            except Exception:
                logger.warning(
                    "checkpointer.deserialize_failed",
                    extra={"checkpoint_id": result.checkpoint_id},
                )
                return None

            # 构建 metadata — 严格匹配 CheckpointMetadata TypedDict
            lg_metadata: dict[str, Any] = {
                "source": result.metadata_.get("source", "loop"),
                "step": result.metadata_.get("step", 0),
                "run_id": result.metadata_.get("run_id", ""),
                "parents": json.loads(result.metadata_.get("parents", "{}")) if result.metadata_.get("parents") else {},
            }

            # 构建 pending_writes
            pending_writes: list[PendingWrite] = []
            pw_raw = result.metadata_.get("pending_writes")
            if pw_raw:
                try:
                    pw_list = json.loads(pw_raw) if isinstance(pw_raw, str) else pw_raw
                    for pw in pw_list:
                        pending_writes.append((pw["channel"], pw["task_id"], pw["value"]))
                except (json.JSONDecodeError, KeyError):
                    pass

            parent_config: RunnableConfig | None = None
            if result.parent_checkpoint_id:
                parent_config = cast(
                    RunnableConfig,
                    {
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": result.parent_checkpoint_id,
                        }
                    },
                )

            return CheckpointTuple(
                config=cast(
                    RunnableConfig,
                    {
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": result.checkpoint_id,
                        }
                    },
                ),
                checkpoint=checkpoint,
                metadata=cast(LGCheckpointMetadata, lg_metadata),
                parent_config=parent_config,
                pending_writes=pending_writes if pending_writes else None,
            )

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """列出 checkpoint 历史。"""
        thread_id = config.get("configurable", {}).get("thread_id", "default") if config else "default"
        checkpoint_ns = config.get("configurable", {}).get("checkpoint_ns", "") if config else ""

        async with self._session_factory()() as session:
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
                    checkpoint = row.state
                except Exception:
                    continue

                lg_metadata: dict[str, Any] = {
                    "source": row.metadata_.get("source", "loop"),
                    "step": row.metadata_.get("step", 0),
                    "run_id": row.metadata_.get("run_id", ""),
                    "parents": json.loads(row.metadata_.get("parents", "{}")) if row.metadata_.get("parents") else {},
                }

                pending_writes: list[PendingWrite] = []
                pw_raw = row.metadata_.get("pending_writes")
                if pw_raw:
                    try:
                        pw_list = json.loads(pw_raw) if isinstance(pw_raw, str) else pw_raw
                        for pw in pw_list:
                            pending_writes.append((pw["channel"], pw["task_id"], pw["value"]))
                    except (json.JSONDecodeError, KeyError):
                        pass

                parent_config: RunnableConfig | None = None
                if row.parent_checkpoint_id:
                    parent_config = cast(
                        RunnableConfig,
                        {
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": row.parent_checkpoint_id,
                            }
                        },
                    )

                yield CheckpointTuple(
                    config=cast(
                        RunnableConfig,
                        {
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": row.checkpoint_id,
                            }
                        },
                    ),
                    checkpoint=checkpoint,
                    metadata=cast(LGCheckpointMetadata, lg_metadata),
                    parent_config=parent_config,
                    pending_writes=pending_writes if pending_writes else None,
                )
