from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.user import CreateUserRequest, UserListResponse, UserResponse
from app.services.users import UserService

router = APIRouter()


@router.post("/users", response_model=UserResponse, summary="创建用户")
async def create_user(
    payload: CreateUserRequest,
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    service = UserService(session)
    return await service.create_user(payload)


@router.get("/users", response_model=UserListResponse, summary="列出用户")
async def list_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = UserService(session)
    items, total = await service.list_users(limit=limit, offset=offset)
    return {"items": items, "total": total}


@router.get("/users/{user_id}", response_model=UserResponse, summary="获取用户详情")
async def get_user(
    user_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    service = UserService(session)
    return await service.get_user(user_id)
