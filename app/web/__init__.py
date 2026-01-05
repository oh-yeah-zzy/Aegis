"""
Web 管理界面路由

提供 Aegis 的前端管理页面
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from pathlib import Path

# 模板目录（项目根目录下的 templates）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))

router = APIRouter()


def get_base_path(request: Request) -> str:
    """
    获取 base path，优先从代理 header 读取

    当通过 Hermes 网关代理访问时，X-Forwarded-Prefix 会包含路径前缀（如 /aegis）
    直接访问时返回空字符串
    """
    forwarded_prefix = request.headers.get("X-Forwarded-Prefix", "").rstrip("/")
    return forwarded_prefix


def get_template_context(request: Request, title: str, active: str) -> dict:
    """生成模板上下文，包含 base_path"""
    base_path = get_base_path(request)
    return {
        "request": request,
        "title": title,
        "active": active,
        "username": "管理员",
        "base_path": base_path,
    }


@router.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页面"""
    base_path = get_base_path(request)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "base_path": base_path},
    )


@router.get("/admin/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """仪表盘页面"""
    return templates.TemplateResponse(
        "dashboard.html", get_template_context(request, "仪表盘", "dashboard")
    )


@router.get("/admin/users", response_class=HTMLResponse)
async def users_page(request: Request):
    """用户管理页面"""
    return templates.TemplateResponse(
        "users.html", get_template_context(request, "用户管理", "users")
    )


@router.get("/admin/roles", response_class=HTMLResponse)
async def roles_page(request: Request):
    """角色管理页面"""
    return templates.TemplateResponse(
        "roles.html", get_template_context(request, "角色管理", "roles")
    )


@router.get("/admin/policies", response_class=HTMLResponse)
async def policies_page(request: Request):
    """认证策略管理页面"""
    return templates.TemplateResponse(
        "policies.html", get_template_context(request, "认证策略", "policies")
    )


@router.get("/admin/audit", response_class=HTMLResponse)
async def audit_page(request: Request):
    """审计日志页面"""
    return templates.TemplateResponse(
        "audit.html", get_template_context(request, "审计日志", "audit")
    )
