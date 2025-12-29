"""
认证策略管理 API

用于管理认证策略（AuthPolicy）
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models.auth_policy import AuthPolicy
from app.core.deps import get_current_superuser

router = APIRouter()


# Pydantic 模式
class AuthPolicyCreate(BaseModel):
    """创建认证策略"""
    name: str = Field(..., min_length=1, max_length=128)
    path_pattern: str = Field(..., min_length=1, max_length=256)
    priority: int = Field(default=0, ge=0)
    auth_required: bool = Field(default=True)
    s2s_required: bool = Field(default=False)
    permission_mode: str = Field(default="any")
    enabled: bool = Field(default=True)
    description: Optional[str] = None


class AuthPolicyUpdate(BaseModel):
    """更新认证策略"""
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    path_pattern: Optional[str] = Field(None, min_length=1, max_length=256)
    priority: Optional[int] = Field(None, ge=0)
    auth_required: Optional[bool] = None
    s2s_required: Optional[bool] = None
    permission_mode: Optional[str] = None
    enabled: Optional[bool] = None
    description: Optional[str] = None


class AuthPolicyResponse(BaseModel):
    """认证策略响应"""
    id: int
    name: str
    path_pattern: str
    priority: int
    auth_required: bool
    s2s_required: bool
    permission_mode: str
    enabled: bool
    description: Optional[str] = None

    class Config:
        from_attributes = True


@router.get(
    "/auth-policies",
    response_model=List[AuthPolicyResponse],
    summary="获取认证策略列表",
)
async def list_auth_policies(
    db: AsyncSession = Depends(get_db),
):
    """获取所有认证策略"""
    result = await db.execute(
        select(AuthPolicy).order_by(AuthPolicy.priority.desc())
    )
    return result.scalars().all()


@router.get(
    "/auth-policies/{policy_id}",
    response_model=AuthPolicyResponse,
    summary="获取认证策略详情",
)
async def get_auth_policy(
    policy_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取单个认证策略"""
    policy = await db.get(AuthPolicy, policy_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="认证策略不存在",
        )
    return policy


@router.post(
    "/auth-policies",
    response_model=AuthPolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建认证策略",
)
async def create_auth_policy(
    data: AuthPolicyCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(get_current_superuser),
):
    """创建新的认证策略"""
    policy = AuthPolicy(**data.model_dump())
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return policy


@router.put(
    "/auth-policies/{policy_id}",
    response_model=AuthPolicyResponse,
    summary="更新认证策略",
)
async def update_auth_policy(
    policy_id: int,
    data: AuthPolicyUpdate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(get_current_superuser),
):
    """更新认证策略"""
    policy = await db.get(AuthPolicy, policy_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="认证策略不存在",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(policy, field, value)

    await db.commit()
    await db.refresh(policy)
    return policy


@router.delete(
    "/auth-policies/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除认证策略",
)
async def delete_auth_policy(
    policy_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(get_current_superuser),
):
    """删除认证策略"""
    policy = await db.get(AuthPolicy, policy_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="认证策略不存在",
        )

    await db.delete(policy)
    await db.commit()
    return None
