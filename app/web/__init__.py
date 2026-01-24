"""
Web 管理界面路由

⚠️ 已迁移到 Vue SPA：所有 Jinja2 页面现在 302 跳转到 Vue 前端
保留这些路由是为了兼容旧链接和 Hermes 网关的登录重定向
"""

from urllib.parse import quote, urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

router = APIRouter()


def get_base_path(request: Request) -> str:
    """
    获取 base path，优先从代理 header 读取

    当通过 Hermes 网关代理访问时，X-Forwarded-Prefix 会包含路径前缀（如 /aegis）
    直接访问时返回空字符串
    """
    forwarded_prefix = request.headers.get("X-Forwarded-Prefix", "").rstrip("/")
    return forwarded_prefix


def get_vue_app_url(request: Request, hash_path: str = "/") -> str:
    """
    构建 Vue SPA 的 URL

    Args:
        request: FastAPI Request 对象
        hash_path: Vue 的 hash 路由路径，如 /login、/users

    Returns:
        完整的 Vue SPA URL，如 /aegis/app/#/login
    """
    base_path = get_base_path(request)
    return f"{base_path}/app/#{hash_path}"


@router.get("/admin/login")
async def login_page(request: Request):
    """
    登录页面 - 302 跳转到 Vue 登录页

    保留 redirect 参数以支持登录后回跳
    """
    base_path = get_base_path(request)
    redirect_param = request.query_params.get("redirect", "")

    # 构建 Vue 登录页 URL
    vue_login_url = f"{base_path}/app/#/login"

    # 如果有 redirect 参数，添加到 URL
    if redirect_param:
        vue_login_url += f"?redirect={quote(redirect_param, safe='')}"

    return RedirectResponse(url=vue_login_url, status_code=302)


@router.post("/admin/login/submit")
async def login_submit(request: Request):
    """
    登录表单提交 - 已废弃，跳转到 Vue 登录页

    Vue 前端直接调用 /api/v1/auth/login，不再使用表单提交
    """
    return RedirectResponse(url=get_vue_app_url(request, "/login"), status_code=302)


@router.get("/admin/")
@router.get("/admin")
async def dashboard_page(request: Request):
    """仪表盘页面 - 302 跳转到 Vue"""
    return RedirectResponse(url=get_vue_app_url(request, "/"), status_code=302)


@router.get("/admin/users")
async def users_page(request: Request):
    """用户管理页面 - 302 跳转到 Vue"""
    return RedirectResponse(url=get_vue_app_url(request, "/users"), status_code=302)


@router.get("/admin/roles")
async def roles_page(request: Request):
    """角色管理页面 - 302 跳转到 Vue"""
    return RedirectResponse(url=get_vue_app_url(request, "/roles"), status_code=302)


@router.get("/admin/policies")
async def policies_page(request: Request):
    """认证策略管理页面 - 302 跳转到 Vue"""
    return RedirectResponse(url=get_vue_app_url(request, "/policies"), status_code=302)


@router.get("/admin/audit")
async def audit_page(request: Request):
    """审计日志页面 - 302 跳转到 Vue"""
    return RedirectResponse(url=get_vue_app_url(request, "/audit"), status_code=302)
