#!/usr/bin/env python3
"""
Aegis 启动脚本

使用 uvicorn 运行应用

用法:
    python run.py                    # 使用默认配置
    python run.py --port 8080        # 指定端口
    python run.py -p 8080 -H 0.0.0.0 # 指定端口和主机（内网可访问）
    python run.py --debug            # 启用调试模式
"""

import argparse
import os

import uvicorn


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Aegis 权限控制网关服务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-p", "--port",
        type=int,
        default=None,
        help="服务端口 (默认: 8000)",
    )

    parser.add_argument(
        "-H", "--host",
        type=str,
        default=None,
        help="监听地址 (默认: 127.0.0.1，仅本地访问)",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        default=None,
        help="启用调试模式",
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        default=None,
        help="启用热重载（开发模式）",
    )

    parser.add_argument(
        "--registry-url",
        type=str,
        default=None,
        help="ServiceAtlas 注册中心地址",
    )

    parser.add_argument(
        "--no-registry",
        action="store_true",
        default=False,
        help="禁用服务注册",
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    # 命令行参数覆盖环境变量
    if args.port is not None:
        os.environ["PORT"] = str(args.port)

    if args.host is not None:
        os.environ["HOST"] = args.host

    if args.debug:
        os.environ["DEBUG"] = "true"

    if args.registry_url is not None:
        os.environ["REGISTRY_URL"] = args.registry_url

    if args.no_registry:
        os.environ["REGISTRY_ENABLED"] = "false"

    # 导入配置（在设置环境变量之后）
    from app.core.config import get_settings

    # 清除缓存，重新加载配置
    get_settings.cache_clear()
    settings = get_settings()

    # 确定是否启用热重载
    reload_enabled = args.reload if args.reload is not None else settings.debug

    print(f"启动 Aegis 服务...")
    print(f"  地址: {settings.host}:{settings.port}")
    print(f"  调试模式: {settings.debug}")
    print(f"  服务注册: {settings.registry_enabled}")
    if settings.registry_enabled:
        print(f"  注册中心: {settings.registry_url}")

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=reload_enabled,
        log_level="debug" if settings.debug else "info",
    )


if __name__ == "__main__":
    main()
