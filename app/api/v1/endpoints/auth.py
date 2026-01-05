"""
认证端点

提供用户登录、登出、令牌刷新等功能

安全特性：
- 登录速率限制（基于 IP 和用户名）
- 账户锁定机制（连续失败后自动锁定）
- 威胁检测（暴力破解、凭据填充）
- 动态 Cookie 安全设置
"""

from datetime import datetime, timedelta, timezone
import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import (
    get_current_user,
    get_current_user_info,
    get_current_user_optional,
    get_db,
)
from app.core.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    TokenError,
)
from app.core.security import verify_password
from app.core.rbac import get_user_permissions, get_user_roles
from app.core.security_config import security_settings
from app.core.rate_limiter import rate_limiter
from app.core.threat_detection import threat_detector
from app.db.models.user import User
from app.db.models.token import RefreshToken
from app.db.models.audit import AuthEvent
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    RefreshResponse,
    CurrentUser,
    ValidateResponse,
)

router = APIRouter(prefix="/auth", tags=["认证"])


def hash_token(token: str) -> str:
    """对令牌进行哈希处理"""
    return hashlib.sha256(token.encode()).hexdigest()


def get_client_ip(request: Request) -> str:
    """
    获取客户端真实 IP 地址

    支持代理场景（X-Forwarded-For、X-Real-IP）
    """
    # 优先从代理头获取
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # 直连场景
    if request.client:
        return request.client.host

    return "unknown"


async def check_login_rate_limit(request: Request, username: str) -> None:
    """
    检查登录速率限制

    Args:
        request: FastAPI 请求对象
        username: 尝试登录的用户名

    Raises:
        HTTPException: 如果超过速率限制
    """
    if not security_settings.rate_limit_enabled:
        return

    client_ip = get_client_ip(request)

    # 检查 IP 级别的速率限制
    ip_key = f"login:ip:{client_ip}"
    allowed, remaining, reset_seconds = await rate_limiter.is_allowed(
        ip_key,
        security_settings.rate_limit_login_max,
        security_settings.rate_limit_login_window,
    )

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"登录尝试过于频繁，请 {reset_seconds} 秒后再试",
            headers={
                "Retry-After": str(reset_seconds),
                "X-RateLimit-Limit": str(security_settings.rate_limit_login_max),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_seconds),
            },
        )

    # 检查用户名级别的速率限制（防止分布式暴力破解）
    if security_settings.rate_limit_login_by_username:
        username_key = f"login:username:{username.lower()}"
        allowed, _, reset_seconds = await rate_limiter.is_allowed(
            username_key,
            security_settings.rate_limit_login_by_username_max,
            security_settings.rate_limit_login_by_username_window,
        )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"该账户登录尝试过于频繁，请 {reset_seconds} 秒后再试",
                headers={"Retry-After": str(reset_seconds)},
            )


async def check_account_lockout(
    username: str,
    db: AsyncSession,
) -> User | None:
    """
    检查账户是否被锁定，并返回用户对象

    Args:
        username: 用户名或邮箱
        db: 数据库会话

    Returns:
        用户对象（如果存在）

    Raises:
        HTTPException: 如果账户被锁定
    """
    # 查询用户
    result = await db.execute(
        select(User).where(
            or_(User.username == username, User.email == username)
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        return None

    # 检查账户锁定状态
    if security_settings.account_lockout_enabled and user.locked_until:
        now = datetime.now(timezone.utc)
        if user.locked_until > now:
            remaining = int((user.locked_until - now).total_seconds())
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"账户已被锁定，请 {remaining} 秒后再试",
                headers={"Retry-After": str(remaining)},
            )
        else:
            # 锁定已过期，重置状态
            user.locked_until = None
            user.failed_login_attempts = 0

    return user


async def handle_login_failure(
    user: User | None,
    username: str,
    request: Request,
    db: AsyncSession,
) -> None:
    """
    处理登录失败

    - 更新失败计数
    - 检查是否需要锁定账户
    - 执行威胁检测
    - 记录审计事件

    Args:
        user: 用户对象（如果存在）
        username: 尝试登录的用户名
        request: FastAPI 请求对象
        db: 数据库会话
    """
    client_ip = get_client_ip(request)
    now = datetime.now(timezone.utc)

    # 更新用户的失败计数
    if user and security_settings.account_lockout_enabled:
        user.failed_login_attempts += 1
        user.last_failed_login_at = now

        # 检查是否需要锁定账户
        if user.failed_login_attempts >= security_settings.account_lockout_threshold:
            user.locked_until = now + timedelta(
                seconds=security_settings.account_lockout_duration
            )

    # 记录失败事件（包含尝试的用户名，用于威胁检测）
    event = AuthEvent(
        event_type="login",
        principal_type="user",
        principal_id=user.id if user else None,
        ip=client_ip,
        user_agent=request.headers.get("user-agent"),
        result="failure",
        failure_reason="用户名或密码错误",
        details={"attempted_username": username},
    )
    db.add(event)
    await db.commit()

    # 执行威胁检测
    await threat_detector.check_and_respond(client_ip, db)
    await db.commit()


def get_cookie_secure() -> bool:
    """
    获取 Cookie 的 Secure 属性值

    优先使用强制设置，否则根据 debug 模式自动判断
    """
    if security_settings.cookie_secure_force is not None:
        return security_settings.cookie_secure_force

    if security_settings.cookie_secure_auto:
        return not settings.debug

    return False


@router.post("/login", response_model=LoginResponse, summary="用户登录")
async def login(
    request: Request,
    response: Response,
    data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    用户登录

    使用用户名/邮箱和密码进行认证，成功后返回访问令牌和刷新令牌。

    安全特性：
    - 登录速率限制（防止暴力破解）
    - 账户锁定机制（连续失败后自动锁定）
    - 威胁检测（自动封禁可疑 IP）
    """
    client_ip = get_client_ip(request)

    # 1. 检查登录速率限制
    await check_login_rate_limit(request, data.username)

    # 2. 检查账户锁定状态（同时获取用户对象）
    user = await check_account_lockout(data.username, db)

    # 3. 验证用户和密码
    if user is None or not verify_password(data.password, user.password_hash):
        # 处理登录失败
        await handle_login_failure(user, data.username, request, db)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    # 4. 检查用户是否被禁用
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    # 5. 登录成功 - 重置失败计数
    if security_settings.account_lockout_reset_on_success:
        user.failed_login_attempts = 0
        user.locked_until = None

    # 6. 获取用户角色和权限
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
        ip=client_ip,
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
        ip=client_ip,
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
        httponly=security_settings.cookie_httponly,
        samesite=security_settings.cookie_samesite,
        secure=get_cookie_secure(),
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
            httponly=security_settings.cookie_httponly,
            samesite=security_settings.cookie_samesite,
            secure=get_cookie_secure(),
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
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    db: Annotated[AsyncSession, Depends(get_db)],
    data: LogoutRequest | None = None,
):
    """
    用户登出

    撤销当前用户的所有刷新令牌，并清除认证 Cookie
    """
    user_id = current_user.id if current_user else None
    source = "access" if current_user else None

    # 如果 access token 无法识别用户，则尝试使用 refresh token（前端可选传入）
    if user_id is None and data and data.refresh_token:
        try:
            payload = decode_token(data.refresh_token)
            if payload.get("type") == "refresh":
                user_id = payload.get("sub")
                source = "refresh"
        except TokenError:
            pass

    # 撤销刷新令牌（无有效会话时保持幂等：仍然返回成功并清理 Cookie）
    revoked_count = 0
    if user_id:
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        tokens = result.scalars().all()

        now = datetime.now(timezone.utc)
        for token in tokens:
            token.revoked_at = now

        revoked_count = len(tokens)

        # 记录事件
        event = AuthEvent(
            event_type="logout",
            principal_type="user",
            principal_id=user_id,
            ip=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            result="success",
            details={"revoked_tokens": revoked_count, "source": source},
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


@router.post("/validate", response_model=ValidateResponse, summary="验证 Token")
async def validate_token(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    验证 JWT Token 是否有效

    供网关（Hermes）调用，用于验证用户的认证状态。
    Token 从 Authorization 头中提取（Bearer 格式）。

    返回:
    - 200: Token 有效，返回用户信息
    - 401: Token 无效或已过期
    """
    # 从请求头提取 Token
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证头",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证头格式错误，应为 Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header[7:]

    try:
        # 解码 Token
        payload = decode_token(token)

        # 检查是否是访问令牌
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌类型无效",
            )

        user_id = payload.get("sub")

        # 查询用户，验证是否存在且未被禁用
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户已被禁用",
            )

        # 检查 token_version 是否匹配（用于令牌撤销）
        token_version = payload.get("token_version")
        if token_version is not None and token_version != user.token_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌已被撤销",
            )

        # Token 有效，返回用户信息
        return ValidateResponse(
            valid=True,
            user_id=user.id,
            username=user.username,
            roles=payload.get("roles", []),
            permissions=payload.get("permissions", []),
        )

    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
