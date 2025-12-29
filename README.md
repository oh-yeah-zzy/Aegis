# Aegis 权限控制网关服务

Aegis 是一个基于 Python + FastAPI 的权限控制网关服务，作为 ServiceAtlas 服务注册中心的入口服务。

## 功能特性

- **用户认证 (JWT)**: 登录/登出、访问令牌和刷新令牌、令牌轮换
- **RBAC 权限控制**: 用户-角色-权限三层结构
- **API 网关鉴权**: 路由匹配、权限校验、代理转发
- **服务间认证**: client_id/client_secret 认证方式
- **审计日志**: 请求日志、认证事件、敏感信息脱敏
- **服务注册**: 自动注册到 ServiceAtlas 并维护心跳

## 快速开始

### 安装依赖

```bash
cd /path/to/Aegis
pip install -r requirements.txt
```

### 启动服务

```bash
python run.py
```

服务启动后：
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

### 默认账户

- 用户名: `admin`
- 密码: `admin123`

> **警告**: 请在生产环境中立即修改默认密码！

## 命令行参数

```bash
python run.py [选项]
```

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--port` | `-p` | 服务端口 | 8000 |
| `--host` | `-H` | 监听地址 | 0.0.0.0 |
| `--debug` | | 启用调试模式 | false |
| `--reload` | | 启用热重载 | false |
| `--registry-url` | | ServiceAtlas 地址 | http://localhost:9000 |
| `--no-registry` | | 禁用服务注册 | false |

### 示例

```bash
# 使用 8080 端口启动
python run.py --port 8080
python run.py -p 8080

# 指定端口和监听地址
python run.py -p 8080 -H 127.0.0.1

# 开发模式（调试 + 热重载）
python run.py --debug --reload

# 指定注册中心地址
python run.py --registry-url http://192.168.1.100:9000

# 禁用服务注册（单独运行）
python run.py --no-registry

# 组合使用
python run.py -p 8080 --registry-url http://localhost:9000 --debug
```

## 环境变量配置

复制 `.env.example` 为 `.env` 并修改配置：

```bash
cp .env.example .env
```

主要配置项：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `PORT` | 服务端口 | 8000 |
| `HOST` | 监听地址 | 0.0.0.0 |
| `DEBUG` | 调试模式 | false |
| `DATABASE_URL` | 数据库连接 | sqlite+aiosqlite:///./aegis.db |
| `JWT_SECRET_KEY` | JWT 密钥 | (需修改) |
| `REGISTRY_ENABLED` | 启用服务注册 | true |
| `REGISTRY_URL` | ServiceAtlas 地址 | http://localhost:9000 |

## 与 ServiceAtlas 集成

### 启动顺序

1. 先启动 ServiceAtlas（端口 9000）
2. 再启动 Aegis（端口 8000）

```bash
# 终端 1: 启动 ServiceAtlas
cd /path/to/ServiceAtlas
python run.py

# 终端 2: 启动 Aegis
cd /path/to/Aegis
python run.py
```

### 验证注册

```bash
curl http://localhost:9000/api/v1/services
```

应该能看到 `aegis` 服务已注册。

## API 端点

### 认证

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/login` | 用户登录 |
| POST | `/api/v1/auth/refresh` | 刷新令牌 |
| POST | `/api/v1/auth/logout` | 用户登出 |
| GET | `/api/v1/auth/me` | 获取当前用户信息 |

### 用户管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/users` | 获取用户列表 |
| POST | `/api/v1/users` | 创建用户 |
| GET | `/api/v1/users/{id}` | 获取用户详情 |
| PATCH | `/api/v1/users/{id}` | 更新用户 |
| DELETE | `/api/v1/users/{id}` | 删除用户 |

### 角色管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/roles` | 获取角色列表 |
| POST | `/api/v1/roles` | 创建角色 |
| PATCH | `/api/v1/roles/{id}` | 更新角色 |
| DELETE | `/api/v1/roles/{id}` | 删除角色 |

### 权限管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/permissions` | 获取权限列表 |
| POST | `/api/v1/permissions` | 创建权限 |
| PATCH | `/api/v1/permissions/{id}` | 更新权限 |
| DELETE | `/api/v1/permissions/{id}` | 删除权限 |

### 服务间认证

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/v1/s2s/token` | 获取服务令牌 |
| GET | `/api/v1/services` | 获取服务列表 |
| POST | `/api/v1/services` | 创建服务 |
| POST | `/api/v1/services/{id}/credentials` | 创建服务凭证 |

### 路由管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/routes` | 获取路由列表 |
| POST | `/api/v1/routes` | 创建路由 |
| PATCH | `/api/v1/routes/{id}` | 更新路由 |
| DELETE | `/api/v1/routes/{id}` | 删除路由 |

### 审计日志

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/audit/logs` | 获取审计日志 |
| GET | `/api/v1/audit/events` | 获取认证事件 |

## Docker 部署

```bash
# 构建镜像
docker build -t aegis .

# 运行容器
docker run -d \
  --name aegis \
  -p 8000:8000 \
  -e JWT_SECRET_KEY=your-secret-key \
  -e REGISTRY_URL=http://service-atlas:9000 \
  aegis

# 使用 docker-compose
docker-compose up -d
```

## 项目结构

```
Aegis/
├── app/
│   ├── main.py              # 应用入口
│   ├── api/v1/              # API 端点
│   │   └── endpoints/       # 各功能端点
│   ├── gateway/             # 网关模块
│   │   ├── matcher.py       # 路由匹配
│   │   ├── proxy.py         # 代理转发
│   │   └── policy.py        # 访问策略
│   ├── core/                # 核心模块
│   │   ├── config.py        # 配置
│   │   ├── jwt.py           # JWT 处理
│   │   ├── rbac.py          # 权限控制
│   │   └── registry.py      # 服务注册
│   ├── db/models/           # 数据库模型
│   ├── schemas/             # Pydantic 模型
│   └── middleware/          # 中间件
├── run.py                   # 启动脚本
├── requirements.txt         # 依赖
├── Dockerfile
└── docker-compose.yml
```

## 技术栈

- Python 3.9+
- FastAPI 0.104+
- SQLAlchemy 2.0 (异步)
- python-jose (JWT)
- passlib (密码哈希)
- httpx (HTTP 客户端)

## 许可证

MIT License
