<div align="center">

# Aegis

**身份认证与访问管理系统**

[![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red?logo=python&logoColor=white)](https://sqlalchemy.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

JWT 认证 · RBAC 权限控制 · 服务间认证 · 审计日志

</div>

---

## 概述

Aegis 是一个基于 Python + FastAPI 的身份认证与访问管理（IAM）系统，为微服务生态提供统一的认证鉴权能力。

### 核心特性

| 特性 | 说明 |
|------|------|
| **JWT 认证** | 登录/登出、访问令牌和刷新令牌、令牌轮换 |
| **RBAC 权限控制** | 用户-角色-权限三层结构 |
| **权限验证 API** | 供其他服务调用验证用户权限 |
| **服务间认证** | client_id/client_secret 认证方式 |
| **审计日志** | 请求日志、认证事件、敏感信息脱敏 |
| **服务注册** | 自动注册到 ServiceAtlas 并维护心跳 |

### 技术栈

- **后端**: Python 3.9+ / FastAPI 0.104+
- **前端**: Vue 3 + Vite（支持中英文切换）/ Jinja2（传统模板）
- **ORM**: SQLAlchemy 2.0 (async)
- **认证**: python-jose (JWT) / passlib (密码哈希)
- **HTTP**: httpx (异步客户端)

---

## 与 Hermes 网关协作

在微服务架构中，Aegis 作为 IAM 系统与 Hermes API 网关协作：

```
用户请求 → Hermes (API网关) → 路由转发 → Aegis (认证鉴权)
                ↓                          ↓
         透传 Authorization 头      验证令牌、检查权限
```

- **Hermes**：负责路由转发、负载均衡、限流熔断（透传模式，不做认证）
- **Aegis**：负责用户认证、权限验证、令牌管理

---

## 快速开始

### 安装依赖

```bash
cd Aegis
pip install -r requirements.txt
```

### 启动服务

```bash
python run.py
```

服务启动后：

| 地址 | 说明 |
|------|------|
| http://localhost:8000/admin | Web 管理界面（Jinja2 传统版） |
| http://localhost:8000/app | Web 管理界面（Vue 新版，需先构建） |
| http://localhost:8000/docs | API 文档 |
| http://localhost:8000/health | 健康检查 |

### 默认账户

| 用户名 | 密码 |
|--------|------|
| `admin` | `admin123` |

> **警告**: 请在生产环境中立即修改默认密码！

---

## 前端开发

Aegis 提供两套前端界面：
- **Vue 3 版本**（推荐）：位于 `frontend/` 目录，支持中英文切换，**所有新功能将只在此版本开发**
- **Jinja2 版本**（⚠️ Deprecated）：位于 `templates/` 目录，仅作为向后兼容保留，未来版本将移除

### Vue 前端开发

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 开发模式（热重载，访问 http://localhost:3002）
npm run dev

# 构建生产版本（输出到 ../static/app/）
npm run build
```

构建完成后，访问 `http://localhost:8000/app` 即可使用 Vue 新版界面。

### 国际化

Vue 前端支持中英文切换：
- 翻译文件位于 `frontend/src/locales/`
- 导航栏右上角提供语言切换按钮
- 语言偏好自动保存到浏览器 localStorage

---

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
| `--registry-url` | | ServiceAtlas 地址 | http://localhost:8888 |
| `--no-registry` | | 禁用服务注册 | false |

### 示例

```bash
# 开发模式（调试 + 热重载）
python run.py --debug --reload

# 指定端口
python run.py -p 8080 -H 127.0.0.1

# 禁用服务注册（单独运行）
python run.py --no-registry

# 指定注册中心地址
python run.py --registry-url http://192.168.1.100:9000
```

---

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
| `JWT_SECRET_KEY` | JWT 密钥 | (自动生成) |
| `REGISTRY_ENABLED` | 启用服务注册 | true |
| `REGISTRY_URL` | ServiceAtlas 地址 | http://localhost:8888 |

---

## 与 ServiceAtlas 集成

### 启动顺序

1. 先启动 ServiceAtlas（端口 8888）
2. 再启动 Aegis（端口 8000）

```bash
# 终端 1: 启动 ServiceAtlas
cd ServiceAtlas && python run.py

# 终端 2: 启动 Aegis
cd Aegis && python run.py
```

### 验证注册

```bash
curl http://localhost:8888/api/v1/services
```

应该能看到 `aegis` 服务已注册。

---

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

---

## Docker 部署

```bash
# 构建镜像
docker build -t aegis .

# 运行容器
docker run -d \
  --name aegis \
  -p 8000:8000 \
  -e JWT_SECRET_KEY=your-secret-key \
  -e REGISTRY_URL=http://service-atlas:8888 \
  aegis

# 使用 docker-compose
docker-compose up -d
```

---

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
├── frontend/                # Vue 3 前端（新增）
│   ├── src/
│   │   ├── views/           # 页面组件
│   │   ├── components/      # 公共组件
│   │   ├── locales/         # 国际化翻译
│   │   ├── router/          # 路由配置（含认证守卫）
│   │   ├── stores/          # Pinia 状态管理
│   │   └── api/             # API 封装（含 JWT 认证）
│   ├── package.json
│   └── vite.config.js
├── templates/               # HTML 模板（传统版）
├── static/                  # 静态资源
│   └── app/                 # Vue 构建输出目录
├── run.py                   # 启动脚本
├── requirements.txt         # 依赖
├── Dockerfile
└── docker-compose.yml
```

---

## 许可证

[MIT License](LICENSE)

---

<div align="center">

**Built with FastAPI & SQLAlchemy**

</div>
