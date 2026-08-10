# 后端 — fastapi-admin

[English](./README.md) · [根目录说明](../README_zh.md)

面向 RBAC 管理后台的异步 FastAPI 服务：认证、用户/角色/权限接口、审计日志与仪表盘统计。

## 技术栈

- Python **3.14**、FastAPI、Uvicorn
- SQLAlchemy **2**（异步）+ **PostgreSQL**（psycopg）+ Alembic
- JWT access token + 持久化 refresh 会话族
- Argon2id（pwdlib），兼容校验/迁移旧 bcrypt 哈希
- 工具：**uv**、ruff、mypy、pytest

## 目录结构

```text
backend/
├── app/
│   ├── api/v1/          # 路由
│   ├── core/            # 配置、数据库、安全、依赖注入
│   ├── crud/            # 数据访问
│   ├── models/          # ORM 模型
│   ├── schemas/         # Pydantic Schema
│   ├── services/        # 会话、清理、限流等
│   └── main.py          # ASGI 应用工厂
├── alembic/             # 迁移
├── tests/
├── init_db.py           # 超管 + 权限种子
├── main.py              # Windows 友好的启动入口
└── .env.example
```

## 环境准备

```bash
cd backend
cp .env.example .env
uv sync
```

本地开发最少配置：

```ini
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/fastapi_admin
ENVIRONMENT=development
BACKEND_CORS_ORIGINS=http://localhost:5173,http://localhost:3000
ALLOWED_HOSTS=localhost,127.0.0.1
```

首次初始化建议配置：

```ini
INIT_SUPERUSER_USERNAME=admin
INIT_SUPERUSER_EMAIL=admin@example.com
INIT_SUPERUSER_PASSWORD=你的强密码
```

```bash
uv run alembic upgrade head
uv run python init_db.py
```

`init_db.py` 会幂等写入与 `require_permission` / 前端 `PERMISSIONS` 对齐的 **16** 条系统权限，**不**创建角色或分配关系。若已有超级管理员则跳过创建。

## 启动

建议使用项目入口（Windows 上使用 SelectorEventLoop，兼容异步 psycopg）：

```bash
uv run python main.py
```

- 接口前缀：`http://localhost:8000/api/v1`
- OpenAPI：`http://localhost:8000/docs`

常用环境变量：

| 变量 | 作用 |
| --- | --- |
| `LOG_LEVEL` | 根日志级别（默认 `info`） |
| `SQL_ECHO` | 仅排查 SQL 时设为 `true` |
| `REGISTRATION_ENABLED` | 是否开放自助注册（默认关闭） |

## 权限码（种子）

| 模块 | 权限码 |
| --- | --- |
| 用户 | `user:read` `user:create` `user:update` `user:delete` `user:assign` `user:reset_password` |
| 角色 | `role:read` `role:create` `role:update` `role:delete` `role:assign` |
| 权限 | `permission:read` `permission:create` `permission:update` `permission:delete` |
| 审计 | `audit:read` |

## 质量检查

```bash
uv run ruff check .
uv run mypy app
uv run pytest
```

## 更多

生产环境、数据库角色与代理配置见 [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md)。
