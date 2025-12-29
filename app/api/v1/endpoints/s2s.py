"""
服务间认证端点

提供服务间认证（Service-to-Service）功能
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, require_permissions
from app.core.jwt import create_access_token
from app.core.security import hash_password, verify_password
from app.db.models.user import User
from app.db.models.service import Service, ServiceCredential
from app.db.models.audit import AuthEvent
from app.schemas.service import (
    ServiceCreate,
    ServiceUpdate,
    ServiceResponse,
    ServiceCredentialCreate,
    ServiceCredentialResponse,
    S2STokenRequest,
    S2STokenResponse,
)

router = APIRouter(prefix="/s2s", tags=["服务间认证"])


def generate_client_id() -> str:
    """生成客户端ID"""
    return f"svc_{uuid4().hex[:16]}"


def generate_client_secret() -> str:
    """生成客户端密钥"""
    return f"secret_{uuid4().hex}"


@router.post("/token", response_model=S2STokenResponse, summary="获取服务令牌")
async def get_service_token(
    request: Request,
    data: S2STokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    服务间认证

    使用客户端ID和密钥获取服务访问令牌
    """
    # 查找凭证
    result = await db.execute(
        select(ServiceCredential).where(ServiceCredential.client_id == data.client_id)
    )
    credential = result.scalar_one_or_none()

    if credential is None:
        # 记录失败事件
        event = AuthEvent(
            event_type="s2s_auth",
            principal_type="service",
            ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent"),
            result="failure",
            failure_reason="客户端ID不存在",
        )
        db.add(event)
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证失败",
        )

    # 检查凭证有效性
    if not credential.is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="凭证已过期或已撤销",
        )

    # 验证密钥
    if not verify_password(data.client_secret, credential.secret_hash):
        event = AuthEvent(
            event_type="s2s_auth",
            principal_type="service",
            principal_id=credential.service_id,
            ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent"),
            result="failure",
            failure_reason="密钥错误",
        )
        db.add(event)
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证失败",
        )

    # 获取服务信息
    result = await db.execute(
        select(Service).where(Service.id == credential.service_id)
    )
    service = result.scalar_one_or_none()

    if service is None or not service.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="服务不存在或已禁用",
        )

    # 创建服务访问令牌
    access_token = create_access_token(
        subject=f"service:{service.id}",
        expires_delta=timedelta(hours=1),  # 服务令牌有效期1小时
        extra_claims={
            "service_code": service.code,
            "service_name": service.name,
            "type": "access",
            "principal_type": "service",
        },
    )

    # 更新最后使用时间
    credential.last_used_at = datetime.now(timezone.utc)

    # 记录成功事件
    event = AuthEvent(
        event_type="s2s_auth",
        principal_type="service",
        principal_id=service.id,
        ip=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent"),
        result="success",
    )
    db.add(event)

    await db.commit()

    return S2STokenResponse(
        access_token=access_token,
        expires_in=3600,  # 1小时
    )


# 服务管理端点

services_router = APIRouter(prefix="/services", tags=["服务管理"])


@services_router.get("", response_model=list[ServiceResponse], summary="获取服务列表")
async def list_services(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:services:read"]))],
):
    """
    获取服务列表
    """
    result = await db.execute(select(Service).order_by(Service.created_at.desc()))
    services = result.scalars().all()

    return [
        ServiceResponse(
            id=s.id,
            code=s.code,
            name=s.name,
            description=s.description,
            is_active=s.is_active,
            owner_user_id=s.owner_user_id,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in services
    ]


@services_router.post(
    "", response_model=ServiceResponse, status_code=201, summary="创建服务"
)
async def create_service(
    data: ServiceCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:services:write"]))],
):
    """
    创建新服务
    """
    # 检查服务码是否已存在
    result = await db.execute(select(Service).where(Service.code == data.code))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="服务码已存在",
        )

    service = Service(
        code=data.code,
        name=data.name,
        description=data.description,
        is_active=data.is_active,
        owner_user_id=data.owner_user_id,
    )
    db.add(service)
    await db.commit()
    await db.refresh(service)

    return ServiceResponse(
        id=service.id,
        code=service.code,
        name=service.name,
        description=service.description,
        is_active=service.is_active,
        owner_user_id=service.owner_user_id,
        created_at=service.created_at,
        updated_at=service.updated_at,
    )


@services_router.get(
    "/{service_id}", response_model=ServiceResponse, summary="获取服务详情"
)
async def get_service(
    service_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:services:read"]))],
):
    """
    获取服务详情
    """
    result = await db.execute(select(Service).where(Service.id == service_id))
    service = result.scalar_one_or_none()

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="服务不存在",
        )

    return ServiceResponse(
        id=service.id,
        code=service.code,
        name=service.name,
        description=service.description,
        is_active=service.is_active,
        owner_user_id=service.owner_user_id,
        created_at=service.created_at,
        updated_at=service.updated_at,
    )


@services_router.post(
    "/{service_id}/credentials",
    response_model=ServiceCredentialResponse,
    status_code=201,
    summary="创建服务凭证",
)
async def create_service_credential(
    service_id: str,
    data: ServiceCredentialCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:services:write"]))],
):
    """
    为服务创建新凭证

    注意：客户端密钥只在创建时返回一次，请妥善保管
    """
    # 检查服务是否存在
    result = await db.execute(select(Service).where(Service.id == service_id))
    service = result.scalar_one_or_none()

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="服务不存在",
        )

    # 生成凭证
    client_id = generate_client_id()
    client_secret = generate_client_secret()

    # 计算过期时间
    expires_at = None
    if data.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_in_days)

    credential = ServiceCredential(
        service_id=service_id,
        type=data.type,
        client_id=client_id,
        secret_hash=hash_password(client_secret),
        kid=str(uuid4()),
        expires_at=expires_at,
    )
    db.add(credential)
    await db.commit()
    await db.refresh(credential)

    return ServiceCredentialResponse(
        id=credential.id,
        service_id=credential.service_id,
        type=credential.type,
        client_id=credential.client_id,
        client_secret=client_secret,  # 只在创建时返回
        kid=credential.kid,
        created_at=credential.created_at,
        expires_at=credential.expires_at,
        revoked_at=credential.revoked_at,
        last_used_at=credential.last_used_at,
    )


@services_router.get(
    "/{service_id}/credentials",
    response_model=list[ServiceCredentialResponse],
    summary="获取服务凭证列表",
)
async def list_service_credentials(
    service_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:services:read"]))],
):
    """
    获取服务的所有凭证
    """
    result = await db.execute(
        select(ServiceCredential)
        .where(ServiceCredential.service_id == service_id)
        .order_by(ServiceCredential.created_at.desc())
    )
    credentials = result.scalars().all()

    return [
        ServiceCredentialResponse(
            id=c.id,
            service_id=c.service_id,
            type=c.type,
            client_id=c.client_id,
            kid=c.kid,
            created_at=c.created_at,
            expires_at=c.expires_at,
            revoked_at=c.revoked_at,
            last_used_at=c.last_used_at,
        )
        for c in credentials
    ]


@services_router.post(
    "/{service_id}/credentials/{credential_id}/revoke",
    summary="撤销服务凭证",
)
async def revoke_service_credential(
    service_id: str,
    credential_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(["aegis:services:write"]))],
):
    """
    撤销服务凭证
    """
    result = await db.execute(
        select(ServiceCredential).where(
            ServiceCredential.id == credential_id,
            ServiceCredential.service_id == service_id,
        )
    )
    credential = result.scalar_one_or_none()

    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="凭证不存在",
        )

    credential.revoked_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": "凭证已撤销"}
