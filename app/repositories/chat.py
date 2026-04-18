from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, GraphCheckpoint, Message, Session, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: str) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        return await self.session.scalar(stmt)

    async def list_users(self, *, limit: int = 50, offset: int = 0) -> Sequence[User]:
        stmt: Select[tuple[User]] = select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.scalars(stmt)
        return result.all()

    async def create(
        self,
        *,
        username: str,
        user_id: str | None = None,
        display_name: str | None = None,
        email: str | None = None,
        is_active: bool = True,
        metadata: dict | None = None,
    ) -> User:
        user = User(id=user_id) if user_id else User()
        user.username = username
        user.display_name = display_name
        user.email = email
        user.is_active = is_active
        user.metadata_ = metadata or {}
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_or_create(self, *, username: str, user_id: str | None = None) -> User:
        user = await self.get_by_id(user_id) if user_id else None
        if user is not None:
            if user.username != username:
                user.username = username
            return user

        existing = await self.get_by_username(username)
        if existing is not None:
            return existing

        user = User(id=user_id) if user_id else User()
        user.username = username
        self.session.add(user)
        try:
            await self.session.flush()
            return user
        except IntegrityError:
            await self.session.rollback()
            existing = await self.get_by_id(user_id) if user_id else None
            if existing is None:
                existing = await self.get_by_username(username)
            if existing is None:
                raise
            return existing


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, session_id: str) -> Session | None:
        return await self.session.get(Session, session_id)

    async def get_or_create(self, *, session_id: str | None, user_id: str, title: str | None = None) -> Session:
        current = await self.get(session_id) if session_id else None
        if current is not None:
            if current.user_id != user_id:
                current.user_id = user_id
            return current

        current = Session(id=session_id) if session_id else Session()
        current.user_id = user_id
        current.title = title
        self.session.add(current)
        await self.session.flush()
        return current


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        user_id: str | None = None,
        model: str | None = None,
        token_usage: dict | None = None,
        metadata: dict | None = None,
    ) -> Message:
        message = Message(
            session_id=session_id,
            user_id=user_id,
            role=role,
            content=content,
            model=model,
            token_usage=token_usage or {},
            metadata_=metadata or {},
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def list_by_session(self, session_id: str, *, limit: int = 50) -> Sequence[Message]:
        stmt: Select[tuple[Message]] = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        result = await self.session.scalars(stmt)
        return result.all()


class GraphCheckpointRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        session_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        parent_checkpoint_id: str | None,
        state: dict,
        metadata: dict | None = None,
    ) -> GraphCheckpoint:
        checkpoint = GraphCheckpoint(
            session_id=session_id,
            checkpoint_ns=checkpoint_ns,
            checkpoint_id=checkpoint_id,
            parent_checkpoint_id=parent_checkpoint_id,
            state=state,
            metadata_=metadata or {},
            created_at=datetime.now(UTC),
        )
        self.session.add(checkpoint)
        await self.session.flush()
        return checkpoint

    async def list_by_session(self, session_id: str, *, limit: int = 20) -> Sequence[GraphCheckpoint]:
        stmt: Select[tuple[GraphCheckpoint]] = (
            select(GraphCheckpoint)
            .where(GraphCheckpoint.session_id == session_id)
            .order_by(GraphCheckpoint.created_at.desc())
            .limit(limit)
        )
        result = await self.session.scalars(stmt)
        return result.all()

    async def get_latest_by_session(self, session_id: str) -> GraphCheckpoint | None:
        stmt: Select[tuple[GraphCheckpoint]] = (
            select(GraphCheckpoint)
            .where(GraphCheckpoint.session_id == session_id)
            .order_by(GraphCheckpoint.created_at.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: str | None,
        action: str,
        resource_type: str,
        resource_id: str | None,
        trace_id: str | None,
        payload: dict,
        created_at: datetime,
    ) -> AuditLog:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            trace_id=trace_id,
            payload=payload,
            created_at=created_at,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry
