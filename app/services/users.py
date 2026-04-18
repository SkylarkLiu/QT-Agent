from __future__ import annotations

from uuid import NAMESPACE_DNS, uuid5

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.chat import AuditLogRepository, UserRepository
from app.schemas.user import CreateUserRequest, UserResponse
from app.services.audit import AuditService


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.audit_service = AuditService(AuditLogRepository(session))

    def _normalize_user_id(self, user_id: str | None, username: str) -> str | None:
        if user_id is None:
            return None
        return str(uuid5(NAMESPACE_DNS, f"qt-agent:user:{user_id}:{username}"))

    async def create_user(self, payload: CreateUserRequest) -> UserResponse:
        try:
            user = await self.user_repo.create(
                username=payload.username,
                user_id=self._normalize_user_id(payload.user_id, payload.username),
                display_name=payload.display_name,
                email=payload.email,
                is_active=payload.is_active,
                metadata=payload.metadata,
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already exists with the same username or email.",
            ) from exc
        await self.audit_service.record(
            action="user.created",
            resource_type="user",
            resource_id=user.id,
            user_id=user.id,
            payload={"username": user.username},
        )
        await self.session.commit()
        return UserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            email=user.email,
            is_active=user.is_active,
            metadata=user.metadata_,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def list_users(self, *, limit: int = 50, offset: int = 0) -> tuple[list[UserResponse], int]:
        users = await self.user_repo.list_users(limit=limit, offset=offset)
        items = [
            UserResponse(
                id=user.id,
                username=user.username,
                display_name=user.display_name,
                email=user.email,
                is_active=user.is_active,
                metadata=user.metadata_,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
            for user in users
        ]
        return items, len(items)

    async def get_user(self, user_id: str) -> UserResponse:
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return UserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            email=user.email,
            is_active=user.is_active,
            metadata=user.metadata_,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
