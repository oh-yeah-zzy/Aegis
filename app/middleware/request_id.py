"""
请求ID中间件

为每个请求添加唯一的请求ID
"""

from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """请求ID中间件"""

    async def dispatch(self, request: Request, call_next) -> Response:
        # 从请求头获取或生成请求ID
        request_id = request.headers.get("X-Request-ID") or str(uuid4())

        # 将请求ID存储到 request.state
        request.state.request_id = request_id

        # 继续处理请求
        response = await call_next(request)

        # 将请求ID添加到响应头
        response.headers["X-Request-ID"] = request_id

        return response
