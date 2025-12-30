"""
认证端点

提供用户登录、登出、令牌刷新等功能
"""

from datetime import datetime, timedelta, timezone
import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user, get_current_user_info, get_db
from app.core.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    TokenError,
)
from app.core.security import verify_password
from app.core.rbac import get_user_permissions, get_user_roles
from app.db.models.user import User
from app.db.models.token import RefreshToken
from app.db.models.audit import AuthEvent
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    CurrentUser,
)

router = APIRouter(prefix="/auth", tags=["认证"])


def hash_token(token: str) -> str:
    """对令牌进行哈希处理"""
    return hashlib.sha256(token.encode()).hexdigest()


@router.post("/login", response_model=LoginResponse, summary="用户登录")
async def login(
    request: Request,
    response: Response,
    data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    用户登录

    使用用户名/邮箱和密码进行认证，成功后返回访问令牌和刷新令牌
    """
    # 查询用户（支持用户名或邮箱登录）
    result = await db.execute(
        select(User).where(
            or_(User.username == data.username, User.email == data.username)
        )
    )
    user = result.scalar_one_or_none()

    # 验证用户和密码
    if user is None or not verify_password(data.password, user.password_hash):
        # 记录失败事件
        event = AuthEvent(
            event_type="login",
            principal_type="user",
            principal_id=user.id if user else None,
            ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent"),
            result="failure",
            failure_reason="用户名或密码错误",
        )
        db.add(event)
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    # 获取用户角色和权限
    roles = await get_user_roles(db, user.id)
    permissions = await get_user_permissions(db, user.id)

    # 创建访问令牌
    access_token = create_access_token(
        subject=user.id,
        extra_claims={
            "username": user.username,
            "roles": list(roles),
            "permissions": list(permissions),
            "token_version": user.token_version,
        },
    )

    # 创建刷新令牌
    refresh_token, jti = create_refresh_token(subject=user.id)

    # 保存刷新令牌到数据库
    refresh_token_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        jti=jti,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.jwt_refresh_token_expire_days),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(refresh_token_record)

    # 更新最后登录时间
    user.last_login_at = datetime.now(timezone.utc)

    # 记录成功事件
    event = AuthEvent(
        event_type="login",
        principal_type="user",
        principal_id=user.id,
        ip=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent"),
        result="success",
    )
    db.add(event)

    await db.commit()

    # 设置 Cookie，用于浏览器直接访问时的认证
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.jwt_access_token_expire_minutes * 60,
        httponly=True,  # 防止 JavaScript 访问，提高安全性
        samesite="lax",  # 防止 CSRF 攻击
        secure=False,  # 生产环境应设置为 True（仅 HTTPS）
        path="/",
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=RefreshResponse, summary="刷新令牌")
async def refresh_token(
    request: Request,
    response: Response,
    data: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    刷新访问令牌

    使用刷新令牌获取新的访问令牌和刷新令牌（令牌轮换）
    """
    try:
        # 解码刷新令牌
        payload = decode_token(data.refresh_token)

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌类型无效",
            )

        jti = payload.get("jti")
        user_id = payload.get("sub")

        # 查找刷新令牌记录
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.jti == jti)
        )
        token_record = result.scalar_one_or_none()

        if token_record is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="刷新令牌不存在",
            )

        if not token_record.is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="刷新令牌已失效",
            )

        # 验证令牌哈希
        if token_record.token_hash != hash_token(data.refresh_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="刷新令牌无效",
            )

        # 查询用户
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在或已被禁用",
            )

        # 获取用户角色和权限
        roles = await get_user_roles(db, user.id)
        permissions = await get_user_permissions(db, user.id)

        # 创建新的访问令牌
        new_access_token = create_access_token(
            subject=user.id,
            extra_claims={
                "username": user.username,
                "roles": list(roles),
                "permissions": list(permissions),
                "token_version": user.token_version,
            },
        )

        # 创建新的刷新令牌（令牌轮换）
        new_refresh_token, new_jti = create_refresh_token(subject=user.id)

        # 撤销旧的刷新令牌
        token_record.revoked_at = datetime.now(timezone.utc)

        # 保存新的刷新令牌
        new_token_record = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(new_refresh_token),
            jti=new_jti,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.jwt_refresh_token_expire_days),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.add(new_token_record)

        # 更新旧令牌的替换记录
        token_record.replaced_by_id = new_token_record.id

        # 记录事件
        event = AuthEvent(
            event_type="refresh",
            principal_type="user",
            principal_id=user.id,
            ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent"),
            result="success",
        )
        db.add(event)

        await db.commit()

        # 更新 Cookie
        response.set_cookie(
            key="access_token",
            value=new_access_token,
            max_age=settings.jwt_access_token_expire_minutes * 60,
            httponly=True,
            samesite="lax",
            secure=False,
            path="/",
        )

        return RefreshResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )

    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.post("/logout", summary="用户登出")
async def logout(
    request: Request,
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    用户登出

    撤销当前用户的所有刷新令牌，并清除认证 Cookie
    """
    # 撤销所有有效的刷新令牌
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    tokens = result.scalars().all()

    now = datetime.now(timezone.utc)
    for token in tokens:
        token.revoked_at = now

    # 记录事件
    event = AuthEvent(
        event_type="logout",
        principal_type="user",
        principal_id=current_user.id,
        ip=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent"),
        result="success",
        details={"revoked_tokens": len(tokens)},
    )
    db.add(event)

    await db.commit()

    # 清除认证 Cookie
    response.delete_cookie(key="access_token", path="/")

    return {"message": "登出成功"}


@router.get("/me", response_model=CurrentUser, summary="获取当前用户信息")
async def get_me(
    current_user_info: Annotated[CurrentUser, Depends(get_current_user_info)],
):
    """
    获取当前用户信息

    返回当前登录用户的详细信息，包括角色和权限
    """
    return current_user_info
