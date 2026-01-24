"""
API v1 路由汇总

汇总所有 v1 版本的 API 端点
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, roles, permissions, s2s, audit, security, stats

# 创建 v1 路由
api_router = APIRouter(prefix="/api/v1")

# 注册各端点路由
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(roles.router)
api_router.include_router(permissions.router)
api_router.include_router(s2s.router)
api_router.include_router(s2s.services_router)
api_router.include_router(audit.router)
api_router.include_router(security.router)
api_router.include_router(stats.router)
