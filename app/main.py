"""
Aegis 主应用入口

IAM 系统 - 身份认证与访问管理
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.api.v1.router import api_router
from app.middleware.request_id import RequestIDMiddleware
from app.web import router as web_router

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    启动时创建数据库表，关闭时清理资源
    """
    # 导入服务注册模块
    from app.core.registry import init_registry_client, shutdown_registry_client

    # 启动时：创建数据库表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 初始化默认数据（如果需要）
    await init_default_data()

    # 注册到 ServiceAtlas 服务注册中心
    await init_registry_client()

    yield

    # 关闭时：从服务注册中心注销
    await shutdown_registry_client()

    # 清理数据库资源
    await engine.dispose()


async def init_default_data():
    """
    初始化默认数据

    创建默认的超级管理员用户、系统角色和权限
    """
    from sqlalchemy import select
    from app.db.session import async_session_maker
    from app.db.models.user import User
    from app.db.models.role import Role, Permission, RolePermission
    from app.db.models.user_role import UserRole
    from app.core.security import hash_password

    async with async_session_maker() as db:
        # 检查是否已有用户
        result = await db.execute(select(User).limit(1))
        if result.scalar_one_or_none():
            return  # 已有数据，跳过初始化

        # 创建默认权限
        permissions_data = [
            # 用户管理权限
            ("aegis:users:read", "查看用户", "aegis", "users", "read"),
            ("aegis:users:write", "编辑用户", "aegis", "users", "write"),
            ("aegis:users:delete", "删除用户", "aegis", "users", "delete"),
            # 角色管理权限
            ("aegis:roles:read", "查看角色", "aegis", "roles", "read"),
            ("aegis:roles:write", "编辑角色", "aegis", "roles", "write"),
            ("aegis:roles:delete", "删除角色", "aegis", "roles", "delete"),
            # 权限管理权限
            ("aegis:permissions:read", "查看权限", "aegis", "permissions", "read"),
            ("aegis:permissions:write", "编辑权限", "aegis", "permissions", "write"),
            ("aegis:permissions:delete", "删除权限", "aegis", "permissions", "delete"),
            # 服务管理权限
            ("aegis:services:read", "查看服务", "aegis", "services", "read"),
            ("aegis:services:write", "编辑服务", "aegis", "services", "write"),
            ("aegis:services:delete", "删除服务", "aegis", "services", "delete"),
            # 审计日志权限
            ("aegis:audit:read", "查看审计日志", "aegis", "audit", "read"),
        ]

        permissions = []
        for code, name, service_code, resource, action in permissions_data:
            permission = Permission(
                code=code,
                name=name,
                service_code=service_code,
                resource=resource,
                action=action,
            )
            db.add(permission)
            permissions.append(permission)

        await db.flush()

        # 创建超级管理员角色
        admin_role = Role(
            code="admin",
            name="超级管理员",
            description="拥有所有权限的超级管理员角色",
            is_system=True,
        )
        db.add(admin_role)
        await db.flush()

        # 为管理员角色分配所有权限
        for permission in permissions:
            role_permission = RolePermission(
                role_id=admin_role.id,
                permission_id=permission.id,
            )
            db.add(role_permission)

        # 创建默认超级管理员用户
        admin_user = User(
            username="admin",
            email="admin@aegis.local",
            password_hash=hash_password("admin123"),
            is_active=True,
            is_superuser=True,
        )
        db.add(admin_user)
        await db.flush()

        # 为管理员用户分配管理员角色
        user_role = UserRole(
            user_id=admin_user.id,
            role_id=admin_role.id,
        )
        db.add(user_role)

        await db.commit()

        print("默认数据初始化完成:")
        print(f"  - 创建了 {len(permissions)} 个权限")
        print(f"  - 创建了超级管理员角色: {admin_role.code}")
        print(f"  - 创建了管理员用户: {admin_user.username} (密码: admin123)")
        print("  - 请在生产环境中修改默认密码!")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
Aegis 身份认证与访问管理（IAM）系统

## 功能特性

- **用户认证**: JWT 令牌认证，支持访问令牌和刷新令牌
- **RBAC 权限控制**: 基于角色的访问控制，用户-角色-权限三层结构
- **权限验证 API**: 供其他服务调用的权限验证接口
- **服务间认证**: 服务间调用的身份验证
- **审计日志**: 记录所有请求和认证事件

## 默认账户

- 用户名: `admin`
- 密码: `admin123`

**请在生产环境中立即修改默认密码！**
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# 添加请求ID中间件
app.add_middleware(RequestIDMiddleware)

# 先定义内置端点（必须在网关路由之前）
@app.get("/health", tags=["健康检查"])
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "service": settings.app_name}


@app.get("/", tags=["根路径"])
async def root(request: Request):
    """根路径 - 重定向到管理界面"""
    from fastapi.responses import RedirectResponse

    # 获取代理前缀（通过 Hermes 访问时会有 X-Forwarded-Prefix header）
    base_path = request.headers.get("X-Forwarded-Prefix", "").rstrip("/")

    # 检查是否已通过 Cookie 登录
    if request.cookies.get("access_token"):
        return RedirectResponse(url=f"{base_path}/admin/")

    return RedirectResponse(url=f"{base_path}/admin/login")


# 注册 API 路由
app.include_router(api_router)

# 挂载静态文件
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# 注册 Web 管理界面路由
app.include_router(web_router)
