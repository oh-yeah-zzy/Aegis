"""
Web 管理界面路由

提供 Aegis 的前端管理页面
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from pathlib import Path

# 模板目录（项目根目录下的 templates）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))

router = APIRouter()


@router.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页面"""
    # 如果用户已通过 Cookie 登录，重定向到管理后台
    if request.cookies.get("access_token"):
        return RedirectResponse(url="/admin/", status_code=302)

    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/admin/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """仪表盘页面"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "title": "仪表盘",
        "active": "dashboard",
        "username": "管理员",
    })


@router.get("/admin/users", response_class=HTMLResponse)
async def users_page(request: Request):
    """用户管理页面"""
    return templates.TemplateResponse("users.html", {
        "request": request,
        "title": "用户管理",
        "active": "users",
        "username": "管理员",
    })


@router.get("/admin/roles", response_class=HTMLResponse)
async def roles_page(request: Request):
    """角色管理页面"""
    return templates.TemplateResponse("roles.html", {
        "request": request,
        "title": "角色管理",
        "active": "roles",
        "username": "管理员",
    })


@router.get("/admin/policies", response_class=HTMLResponse)
async def policies_page(request: Request):
    """认证策略管理页面"""
    return templates.TemplateResponse("policies.html", {
        "request": request,
        "title": "认证策略",
        "active": "policies",
        "username": "管理员",
    })


@router.get("/admin/audit", response_class=HTMLResponse)
async def audit_page(request: Request):
    """审计日志页面"""
    return templates.TemplateResponse("audit.html", {
        "request": request,
        "title": "审计日志",
        "active": "audit",
        "username": "管理员",
    })


@router.get("/admin/portal", response_class=HTMLResponse)
async def portal_page(request: Request):
    """服务目录页面"""
    return templates.TemplateResponse("portal.html", {
        "request": request,
        "title": "服务目录",
        "active": "portal",
        "username": "管理员",
    })
