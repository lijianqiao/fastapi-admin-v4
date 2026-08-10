# fastapi-admin

[English](./README.md)

基于 **FastAPI + React** 的全栈 **RBAC 管理后台**：用户 / 角色 / 权限、JWT 双 Token、可撤销会话，以及接口级权限校验。

![登录页](./docs/images/login.png)

## 界面预览

| 仪表盘 | 用户管理 |
| --- | --- |
| ![仪表盘](./docs/images/dashboard.png) | ![用户管理](./docs/images/users.png) |

| 角色管理 | 权限管理 |
| --- | --- |
| ![角色管理](./docs/images/roles.png) | ![权限管理](./docs/images/permissions.png) |

![操作日志](./docs/images/audit.png)

## 功能特性

- **RBAC**：用户 ↔ 角色 ↔ 权限，软删除，按模块分组的权限码（如 `user:read`、`role:assign`）
- **认证安全**：Argon2id 密码、短期 access token、HttpOnly refresh Cookie、会话族轮换与重放撤销
- **接口鉴权**：`require_permission("…")`；`/me` 返回扁平权限列表供前端按钮/路由控制
- **管理能力**：仪表盘、用户/角色/权限 CRUD、角色分配、管理员重置密码、审计日志
- **初始化**：Alembic 迁移 + `init_db.py` 种子写入 16 条系统权限（角色与分配在 UI 中完成）

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 后端 | Python 3.14、FastAPI、SQLAlchemy 2（异步）、PostgreSQL、Alembic、JWT、uv |
| 前端 | React 19、TypeScript、Vite、Tailwind CSS 4、shadcn/ui（Base UI）、Zustand、React Router 7 |
| 质量 | ruff、mypy、pytest / ESLint、Prettier、`tsc -b` |

## 仓库结构

```text
fastapi-admin/
├── backend/          # FastAPI 接口（见 backend/README_zh.md）
├── frontend/         # React 前端（见 frontend/README_zh.md）
├── docs/             # PRD、架构、部署与截图
├── README.md         # 英文
└── README_zh.md      # 中文（本文件）
```

## 快速开始

### 环境要求

- Python **3.14**
- Node.js **≥ 18**（pnpm 或 npm）
- PostgreSQL **≥ 14**（建议预装 `pg_trgm`）
- [uv](https://github.com/astral-sh/uv)

### 1. 后端

```bash
cd backend
cp .env.example .env
# 配置 DATABASE_URL；首次初始化时配置 INIT_SUPERUSER_*
uv sync
uv run alembic upgrade head
uv run python init_db.py
uv run python main.py
```

接口：`http://localhost:8000` · 文档：`http://localhost:8000/docs`

### 2. 前端

```bash
cd frontend
cp .env.example .env
# VITE_API_BASE_URL=http://localhost:8000/api/v1
pnpm install   # 或 npm install
pnpm run dev   # 或 npm run dev
```

应用：`http://localhost:5173`

使用 `init_db.py` 创建的超级管理员登录后，在界面中创建角色并分配权限。

## 文档

| 文档 | 说明 |
| --- | --- |
| [docs/PRD.md](./docs/PRD.md) | 产品需求 |
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | 架构设计 |
| [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) | 生产部署 |
| [backend/README_zh.md](./backend/README_zh.md) | 后端说明（[English](./backend/README.md)） |
| [frontend/README_zh.md](./frontend/README_zh.md) | 前端说明（[English](./frontend/README.md)） |

## 许可证

[MIT](./LICENSE) © lijianqiao
