# 权限管理系统 — 架构设计文档

> **项目名称**: fastapi-admin
> **文档版本**: v1.1（后端安全与异步化修订）
> **撰写人**: 李剑桥（架构师）
> **日期**: 2026-08-09
> **基于**: PRD v1.0

---

## 目录

- [Part A: 系统设计](#part-a-系统设计)
  - [1. 实现方案](#1-实现方案)
  - [2. 文件列表](#2-文件列表)
  - [3. 数据结构和接口](#3-数据结构和接口)
  - [4. 程序调用流程](#4-程序调用流程)
  - [5. 待明确事项](#5-待明确事项)
- [Part B: 任务分解](#part-b-任务分解)
  - [6. 依赖包列表](#6-依赖包列表)
  - [7. 任务列表](#7-任务列表)
  - [8. 共享知识](#8-共享知识)
  - [9. 任务依赖图](#9-任务依赖图)

---

## Part A: 系统设计

### 1. 实现方案

#### 1.1 核心技术挑战

| # | 挑战 | 应对方案 |
|---|------|----------|
| C1 | **Python 3.14 与异步 I/O** | 后端采用 SQLAlchemy `AsyncSession` + psycopg 3 异步接口；Windows 启动入口显式使用 Selector loop；Alembic 独立使用 psycopg 同步连接，避免迁移 CLI 受事件循环限制 |
| C2 | **RBAC 权限校验** — 需在 API 端点级别实现声明式权限控制 | 通过 FastAPI `Depends` 机制实现 `require_permission("xxx")` 依赖注入工厂，从 JWT 解析用户后查询其所有角色的权限码集合，匹配校验 |
| C3 | **JWT 双 Token 机制** — access_token 短期有效，refresh_token 存 httpOnly cookie | 数据库保存 refresh token 摘要与固定会话族锁行；轮换一次性消费，有效期内的旧 token 重放会原子撤销整族，logout/改密/停用可即时撤销 access 会话 |
| C4 | **前后端分离的 CSRF/XSS 防护** — Cookie 写入与刷新均需验证来源 | refresh cookie 使用 `HttpOnly + SameSite=Strict + Secure`；login/register/refresh/logout 校验 Origin/Referer/Sec-Fetch-Site；CORS、Host 与可信代理均使用显式白名单 |
| C5 | **软删除与关联数据一致性** — 用户/角色/权限采用软删除，查询需过滤 `is_deleted` | 在 CRUD 基类中统一处理软删除过滤；删除角色前校验是否有关联用户 |
| C6 | **审计日志无侵入记录** — 关键操作需记录审计日志但不污染业务代码 | 提供统一的 `log_audit()` 工具函数，在 API 路由层显式调用，传入操作类型、目标、详情、IP |

#### 1.2 框架选型

**后端（Python 3.14.3）**

| 框架/库 | 版本 | 用途 | 选型理由 |
|---------|------|------|----------|
| FastAPI | latest | Web 框架 | 原生支持 Pydantic v2、自动 OpenAPI 文档、依赖注入系统 |
| SQLAlchemy | 2.x | 异步 ORM | `AsyncSession` 贯穿 API/CRUD，写操作在请求边界单次提交 |
| psycopg | 3.x | PostgreSQL 驱动 | 同一驱动提供运行时异步连接和 Alembic 同步连接 |
| Alembic | 1.x | 数据库迁移 | SQLAlchemy 官方迁移工具，自动生成迁移脚本 |
| Pydantic Settings | 2.x | 配置管理 | 从 `.env` 读取配置，类型安全 |
| PyJWT | 2.x | JWT 签发/验证 | 校验 issuer、audience、jti、类型、版本与会话族 |
| pwdlib[argon2,bcrypt] | 0.3+ | 密码哈希 | 新密码使用 Argon2id；旧 bcrypt 登录后渐进迁移 |
| python-multipart | latest | 表单解析 | FastAPI 登录接口 OAuth2PasswordRequestForm 依赖 |
| ruff | latest | 代码检查 | 替代 flake8/isort，极快 |
| mypy | latest | 类型检查 | 静态类型安全 |
| pytest | latest | 单元测试 | Python 标准测试框架 |
| httpx | latest | 测试 HTTP 客户端 | FastAPI TestClient 底层依赖 |

**前端（React 19 + TypeScript）**

| 框架/库 | 版本 | 用途 | 选型理由 |
|---------|------|------|----------|
| react-router | 7.x | 路由 | v7 合并了 react-router-dom，API 简洁；支持 loader/action |
| zustand | 5.x | 状态管理 | 轻量、无 boilerplate、TypeScript 友好 |
| axios | 1.x | HTTP 客户端 | 拦截器机制完善，适合 token 自动刷新 |
| react-hook-form | 7.x | 表单管理 | 性能优秀（非受控），与 zod 集成好 |
| @hookform/resolvers | latest | RHF + zod 桥接 | react-hook-form 官方推荐的 schema resolver |
| zod | 3.x | Schema 验证 | 前后端可共享验证规则，TypeScript 类型推导 |
| dayjs | 1.x | 日期处理 | 轻量替代 moment.js，API 兼容 |
| @tanstack/react-table | 8.x | 数据表格 | Headless 设计，配合 shadcn UI 灵活定制 |

> **shadcn 组件**通过 `npx shadcn add <component>` 添加，不走 npm install。需要的组件列表见 [6.3 shadcn 组件清单](#63-shadcn-组件清单)。

#### 1.3 架构模式

**后端 — 分层架构**

```
┌──────────────────────────────────────┐
│           API Layer (api/)            │  ← 路由、请求/响应处理、权限校验
├──────────────────────────────────────┤
│          CRUD Layer (crud/)           │  ← 数据访问、业务查询逻辑
├──────────────────────────────────────┤
│         Model Layer (models/)         │  ← SQLAlchemy ORM 模型
├──────────────────────────────────────┤
│    Core / Infra (core/, utils/)       │  ← 配置、安全、依赖注入、工具
└──────────────────────────────────────┘
```

- **Schema 层（schemas/）**：Pydantic v2 模型，负责请求体验证和响应序列化，与 ORM 模型解耦
- **依赖注入**：FastAPI `Depends` 机制贯穿全链路 — `get_db` → `get_current_user` → `require_permission`

**前端 — 特性驱动分层**

```
┌──────────────────────────────────────┐
│          Pages (pages/)               │  ← 页面组件，路由级
├──────────────────────────────────────┤
│     Components (components/)           │  ← 布局、通用、业务组件
├──────────────────────────────────────┤
│    Hooks / Store (hooks/, store/)      │  ← 状态管理、自定义逻辑
├──────────────────────────────────────┤
│  Lib / Types (lib/, types/)            │  ← API 客户端、类型定义、工具
└──────────────────────────────────────┘
```

---

### 2. 文件列表

#### 2.1 后端文件（`backend/`）

| # | 文件路径 | 说明 | 状态 |
|---|---------|------|------|
| 1 | `backend/pyproject.toml` | 项目依赖与配置（uv） | 修改 |
| 2 | `backend/main.py` | Uvicorn 启动入口 | 修改 |
| 3 | `backend/.env.example` | 环境变量模板 | 新增 |
| 4 | `backend/alembic.ini` | Alembic 迁移配置 | 新增 |
| 5 | `backend/app/__init__.py` | 应用包初始化 | 新增 |
| 6 | `backend/app/main.py` | FastAPI 应用创建、中间件、路由注册 | 新增 |
| 7 | `backend/app/core/__init__.py` | core 包初始化 | 新增 |
| 8 | `backend/app/core/config.py` | Pydantic Settings 配置类 | 新增 |
| 9 | `backend/app/core/database.py` | SQLAlchemy AsyncEngine + AsyncSessionLocal | 新增 |
| 10 | `backend/app/core/security.py` | JWT 签发/验证、Argon2id 哈希与旧 bcrypt 迁移 | 新增 |
| 11 | `backend/app/core/deps.py` | 依赖注入：get_db, get_current_user, require_permission | 新增 |
| 11a | `backend/app/core/cookies.py` | 集中的 refresh cookie 策略（属性签发/清除一致） | 新增 |
| 12 | `backend/app/models/__init__.py` | 模型包初始化，导出所有模型 | 新增 |
| 13 | `backend/app/models/base.py` | Base 声明类 + TimestampMixin | 新增 |
| 14 | `backend/app/models/user.py` | User + UserRole 模型 | 新增 |
| 15 | `backend/app/models/role.py` | Role + RolePermission 模型 | 新增 |
| 16 | `backend/app/models/permission.py` | Permission 模型 | 新增 |
| 17 | `backend/app/models/audit_log.py` | AuditLog 模型 | 新增 |
| 17a | `backend/app/models/refresh_session_family.py` | RefreshSessionFamily：整族锁与撤销真源 | 新增 |
| 17b | `backend/app/models/refresh_session.py` | RefreshSession：token 摘要与轮换历史 | 新增 |
| 18 | `backend/app/schemas/__init__.py` | Schema 包初始化 | 新增 |
| 19 | `backend/app/schemas/common.py` | 通用 Schema：分页、统一响应 | 新增 |
| 20 | `backend/app/schemas/auth.py` | 认证 Schema：注册、登录、Token | 新增 |
| 21 | `backend/app/schemas/user.py` | 用户 Schema：CRUD + 角色分配 | 新增 |
| 22 | `backend/app/schemas/role.py` | 角色 Schema：CRUD + 权限分配 | 新增 |
| 23 | `backend/app/schemas/permission.py` | 权限 Schema：CRUD | 新增 |
| 24 | `backend/app/schemas/audit_log.py` | 审计日志 Schema | 新增 |
| 25 | `backend/app/schemas/dashboard.py` | 仪表盘统计 Schema | 新增 |
| 26 | `backend/app/crud/__init__.py` | CRUD 包初始化，导出实例 | 新增 |
| 27 | `backend/app/crud/base.py` | CRUDBase 泛型基类 | 新增 |
| 28 | `backend/app/crud/user.py` | 用户 CRUD + 权限查询 | 新增 |
| 29 | `backend/app/crud/role.py` | 角色 CRUD + 权限分配 | 新增 |
| 30 | `backend/app/crud/permission.py` | 权限 CRUD | 新增 |
| 31 | `backend/app/crud/audit_log.py` | 审计日志 CRUD | 新增 |
| 31a | `backend/app/crud/dashboard.py` | 仪表盘计数聚合（单次往返） | 新增 |
| 31b | `backend/app/services/__init__.py` | 服务层包初始化 | 新增 |
| 31c | `backend/app/services/auth.py` | 登录限流、会话族轮换/撤销、会话+权限联合查询 | 新增 |
| 31d | `backend/app/services/session_cleanup.py` | refresh 历史分批清理（`SKIP LOCKED`） | 新增 |
| 32 | `backend/app/api/__init__.py` | API 包初始化 | 新增 |
| 33 | `backend/app/api/router.py` | 路由聚合器 | 新增 |
| 34 | `backend/app/api/v1/__init__.py` | v1 包初始化 | 新增 |
| 35 | `backend/app/api/v1/auth.py` | 认证路由：register, login, refresh, logout | 新增 |
| 36 | `backend/app/api/v1/users.py` | 用户路由：CRUD + 角色分配 | 新增 |
| 37 | `backend/app/api/v1/roles.py` | 角色路由：CRUD + 权限分配 | 新增 |
| 38 | `backend/app/api/v1/permissions.py` | 权限路由：CRUD | 新增 |
| 39 | `backend/app/api/v1/me.py` | 个人路由：profile, password | 新增 |
| 40 | `backend/app/api/v1/dashboard.py` | 仪表盘路由 | 新增 |
| 41 | `backend/app/api/v1/audit_logs.py` | 审计日志路由 | 新增 |
| 42 | `backend/app/utils/__init__.py` | utils 包初始化 | 新增 |
| 43 | `backend/app/utils/audit.py` | 审计日志工具函数 | 新增 |
| 44 | `backend/alembic/env.py` | Alembic 环境配置 | 新增 |
| 45 | `backend/alembic/script.py.mako` | 迁移脚本模板 | 新增 |
| 46 | `backend/alembic/versions/.gitkeep` | 迁移版本目录占位 | 新增 |
| 46a | `backend/alembic/versions/*_init.py` 等 4 个版本 | 初始 schema、异步认证加固、在线并发建索引 | 新增 |
| 46b | `backend/init_db.py` | 一次性超级管理员初始化（advisory lock + 审计） | 新增 |
| 46c | `backend/cleanup_sessions.py` | refresh 历史清理 CLI 入口 | 新增 |
| 47 | `backend/tests/__init__.py` | 测试包初始化 | 新增 |
| 48 | `backend/tests/conftest.py` | pytest fixtures（测试 DB、客户端） | 新增 |
| 49 | `backend/tests/test_auth.py` | 认证模块测试 | 新增 |
| 50 | `backend/tests/test_users.py` | 用户模块测试 | 新增 |
| 51 | `backend/tests/test_roles.py` | 角色模块测试 | 新增 |
| 52 | `backend/tests/test_permissions.py` | 权限模块测试 | 新增 |
| 53 | `backend/tests/test_audit.py` | 审计日志测试 | 新增 |

#### 2.2 前端文件（`frontend/`）

| # | 文件路径 | 说明 | 状态 |
|---|---------|------|------|
| 54 | `frontend/.env.example` | 环境变量模板（VITE_API_BASE_URL） | 新增 |
| 55 | `frontend/src/main.tsx` | 入口文件，挂载 Router + ThemeProvider | 修改 |
| 56 | `frontend/src/App.tsx` | 路由定义 + 路由守卫 | 修改 |
| 57 | `frontend/src/types/api.ts` | API 统一响应类型 | 新增 |
| 58 | `frontend/src/types/auth.ts` | 认证类型（Login, Token, UserInfo） | 新增 |
| 59 | `frontend/src/types/user.ts` | 用户类型 | 新增 |
| 60 | `frontend/src/types/role.ts` | 角色类型 | 新增 |
| 61 | `frontend/src/types/permission.ts` | 权限类型 | 新增 |
| 62 | `frontend/src/types/audit.ts` | 审计日志类型 | 新增 |
| 63 | `frontend/src/types/index.ts` | 类型统一导出 | 新增 |
| 64 | `frontend/src/lib/api.ts` | Axios 实例 + 拦截器（JWT 携带、401 刷新） | 新增 |
| 65 | `frontend/src/lib/constants.ts` | 常量定义（路由路径、权限码、存储 key） | 新增 |
| 66 | `frontend/src/store/auth.ts` | Zustand auth store（token, user, permissions） | 新增 |
| 67 | `frontend/src/hooks/use-auth.ts` | 认证 hook（login, logout, refresh） | 新增 |
| 68 | `frontend/src/hooks/use-permission.ts` | 权限校验 hook（hasPermission） | 新增 |
| 69 | `frontend/src/components/layout/AppLayout.tsx` | 主布局（侧边栏 + 顶栏 + Outlet） | 新增 |
| 70 | `frontend/src/components/layout/Sidebar.tsx` | 侧边导航栏（响应式抽屉） | 新增 |
| 71 | `frontend/src/components/layout/Header.tsx` | 顶部栏（面包屑 + 用户菜单 + 主题切换） | 新增 |
| 72 | `frontend/src/components/layout/PageHeader.tsx` | 页面标题组件 | 新增 |
| 73 | `frontend/src/components/auth/ProtectedRoute.tsx` | 路由守卫（登录校验 + 权限校验） | 新增 |
| 74 | `frontend/src/components/common/DataTable.tsx` | 通用数据表格（TanStack Table + shadcn） | 新增 |
| 75 | `frontend/src/components/common/Pagination.tsx` | 分页组件 | 新增 |
| 76 | `frontend/src/components/common/ConfirmDialog.tsx` | 删除确认对话框 | 新增 |
| 77 | `frontend/src/components/common/ErrorBoundary.tsx` | 错误边界 | 新增 |
| 78 | `frontend/src/components/users/UserFormDialog.tsx` | 用户新增/编辑对话框 | 新增 |
| 79 | `frontend/src/components/users/AssignRolesDialog.tsx` | 用户角色分配对话框 | 新增 |
| 80 | `frontend/src/components/roles/RoleFormDialog.tsx` | 角色新增/编辑对话框 | 新增 |
| 81 | `frontend/src/components/roles/AssignPermissionsDialog.tsx` | 角色权限分配对话框 | 新增 |
| 82 | `frontend/src/pages/LoginPage.tsx` | 登录页 | 新增 |
| 83 | `frontend/src/pages/DashboardPage.tsx` | 仪表盘页 | 新增 |
| 84 | `frontend/src/pages/UsersPage.tsx` | 用户管理页 | 新增 |
| 85 | `frontend/src/pages/RolesPage.tsx` | 角色管理页 | 新增 |
| 86 | `frontend/src/pages/PermissionsPage.tsx` | 权限管理页 | 新增 |
| 87 | `frontend/src/pages/ProfilePage.tsx` | 个人中心页 | 新增 |
| 88 | `frontend/src/pages/AuditLogsPage.tsx` | 审计日志页 | 新增 |
| 89 | `frontend/src/pages/ForbiddenPage.tsx` | 403 页 | 新增 |
| 90 | `frontend/src/pages/NotFoundPage.tsx` | 404 页 | 新增 |

#### 2.3 根目录文件

| # | 文件路径 | 说明 | 状态 |
|---|---------|------|------|
| 91 | `.gitignore` | Git 忽略规则（只跟踪源代码） | 修改 |

> **文件总数**: 103（后端 65 + 前端 37 + 根目录 1）
> **新增**: 97 | **修改**: 6（pyproject.toml, backend/main.py, frontend/src/main.tsx, frontend/src/App.tsx, .gitignore, 以及已有的 components/ui/button.tsx 不计）
>
> 带字母后缀的条目是 v1.1 异步安全加固新增的文件，编号沿用原表以保持与 T01–T05 的对应关系。

---

### 3. 数据结构和接口

> 完整 Mermaid 类图见 `docs/class-diagram.mermaid`

```mermaid
classDiagram
    direction TB

    %% ===== 基础模型 =====
    class TimestampMixin {
        +datetime created_at
        +datetime updated_at
    }

    class Base {
        <<SQLAlchemy DeclarativeBase>>
    }

    %% ===== 业务模型 =====
    class User {
        +int id
        +str username
        +str email
        +str hashed_password
        +str nickname
        +bool is_active
        +bool is_deleted
        +bool is_superuser
        +int token_version
        +datetime created_at
        +datetime updated_at
        +roles: Mapped[list[Role]]
    }

    class Role {
        +int id
        +str name
        +str description
        +bool is_deleted
        +datetime created_at
        +datetime updated_at
        +permissions: Mapped[list[Permission]]
        +users: Mapped[list[User]]
    }

    class Permission {
        +int id
        +str name
        +str code
        +str module
        +str description
        +bool is_deleted
        +datetime created_at
        +datetime updated_at
        +roles: Mapped[list[Role]]
    }

    class UserRole {
        +int user_id
        +int role_id
        +datetime created_at
    }

    class RolePermission {
        +int role_id
        +int permission_id
        +datetime created_at
    }

    class AuditLog {
        +int id
        +int user_id
        +str action
        +str target
        +str detail
        +str ip
        +datetime created_at
    }

    class RefreshSessionFamily {
        +str id
        +int user_id
        +int token_version
        +datetime expires_at
        +datetime revoked_at
        +str revoked_reason
    }

    class RefreshSession {
        +int id
        +int user_id
        +str jti
        +str family_id
        +str token_hash
        +datetime expires_at
        +datetime revoked_at
    }

    Base <|-- User : inherits
    Base <|-- Role : inherits
    Base <|-- Permission : inherits
    Base <|-- AuditLog : inherits
    Base <|-- RefreshSessionFamily : inherits
    Base <|-- RefreshSession : inherits
    TimestampMixin <|-- User : mixin
    TimestampMixin <|-- Role : mixin
    TimestampMixin <|-- Permission : mixin

    User "1" --o "*" UserRole : user_id
    Role "1" --o "*" UserRole : role_id
    Role "1" --o "*" RolePermission : role_id
    Permission "1" --o "*" RolePermission : permission_id
    User "1" --o "*" AuditLog : user_id
    User "1" --o "*" RefreshSessionFamily : user_id
    RefreshSessionFamily "1" --o "*" RefreshSession : family_id

    %% ===== CRUD 层 =====
    class CRUDBase~T~ {
        +model: type[T]
        +create(db: AsyncSession, obj: dict) Awaitable[T]
        +get(db: AsyncSession, id: int) Awaitable[T | None]
        +get_multi(db: AsyncSession, skip: int, limit: int) Awaitable[list[T]]
        +update(db: AsyncSession, id: int, obj: dict) Awaitable[T | None]
        +soft_delete(db: AsyncSession, id: int) Awaitable[bool]
    }

    class CRUDUser {
        +get_by_username(db, username: str) User | None
        +get_by_email(db, email: str) User | None
        +create(db, obj: UserCreate) User
        +update(db, id: int, obj: UserUpdate) User | None
        +get_multi_filtered(db, search, is_active, role_id, skip, limit) list[User]
        +assign_roles(db, user_id: int, role_ids: list[int]) User
        +get_permission_codes(db, user_id: int) list[str]
        +permission_exists(user_id: int, code: str) Exists$
        +has_permission(db, user_id: int, code: str) bool
        +authenticate(db, username: str, password: str) User | None
        +change_password(db, user_id, old, new) bool
    }

    class CRUDRole {
        +get_by_name(db, name: str) Role | None
        +assign_permissions(db, role_id: int, permission_ids: list[int]) Role
        +get_user_count(db, role_id: int) int
        +get_permission_ids(db, role_id: int) list[int]
    }

    class CRUDPermission {
        +get_by_code(db, code: str) Permission | None
        +get_by_module(db, module: str) list[Permission]
        +get_all_grouped(db) dict[str, list[Permission]]
    }

    class CRUDAuditLog {
        +create(db, obj: AuditLogCreate) AuditLog
        +get_multi_filtered(db, user_id, action, skip, limit) list[AuditLog]
    }

    CRUDBase <|-- CRUDUser
    CRUDBase <|-- CRUDRole
    CRUDBase <|-- CRUDPermission

    %% ===== 核心服务 =====
    class SecurityUtils {
        +hash_password(password: str) str$
        +verify_and_update_password(plain: str, hashed: str) PasswordVerification$
        +create_access_token(subject: str) str$
        +issue_refresh_token(subject: str) IssuedRefreshToken$
        +decode_token(token: str) dict$
    }

    class Settings {
        +str DATABASE_URL
        +str SECRET_KEY
        +int ACCESS_TOKEN_EXPIRE_MINUTES
        +int REFRESH_TOKEN_EXPIRE_DAYS
        +int PASSWORD_HASH_MAX_CONCURRENCY
        +str ALGORITHM
        +int DB_POOL_SIZE
        +int DB_MAX_OVERFLOW
        +str BACKEND_CORS_ORIGINS
        +str COOKIE_SECURE
    }

    class Dependencies {
        +get_db() AsyncIterator[AsyncSession]$
        +get_current_user(token: str, db: AsyncSession) Awaitable[User]$
        +require_permission(code: str) Callable$
    }

    %% ===== 服务层 =====
    class AuthService {
        +authenticate_user(db, identifier, password) User | None$
        +create_login_session(db, user) SessionTokens$
        +rotate_refresh_session(db, raw_token, claims) SessionTokens$
        +revoke_refresh_session(db, raw_token, claims, reason) int | None$
        +revoke_all_refresh_sessions(db, user_id, reason) void$
        +get_active_session_user(db, user_id, family_id, token_version) User | None$
        +get_authorized_session_user(db, user_id, family_id, token_version, permission_code) AuthorizedUser | None$
    }

    class AuthorizedUser {
        +user: User
        +has_permission: bool
    }

    class LoginRateLimiter {
        +hit(client_ip: str, identifier: str) int | None
        +clear(client_ip: str, identifier: str) void
        +reset() void
    }

    %% ===== 工具函数 =====
    class AuditHelper {
        +log(db: AsyncSession, user_id: int, action: str, target: str, detail: str, ip: str) Awaitable[void]$
    }

    %% ===== 依赖关系 =====
    CRUDUser --> SecurityUtils : authenticate
    Dependencies --> SecurityUtils : decode_token
    Dependencies --> AuthService : 会话与权限一次校验
    AuthService --> CRUDUser : permission_exists / authenticate
    AuthService --> SecurityUtils : 签发与轮换
    AuthService --> RefreshSessionFamily : 整族锁与撤销
    AuthService --> RefreshSession : 摘要与轮换历史
    AuthService --> LoginRateLimiter : 登录/注册限流
    AuthService ..> AuthorizedUser : 返回
    AuditHelper --> CRUDAuditLog : create
```

> `revoke_all_refresh_sessions` 是 `users.token_version` 递增的唯一入口：停用、删除和改密都经由它撤销会话，调用方不得自行递增。

---

### 4. 程序调用流程

> 完整 Mermaid 时序图见 `docs/sequence-diagram.mermaid`

#### 4.1 登录流程

```mermaid
sequenceDiagram
    participant C as Client
    participant API as AuthAPI
    participant AS as AuthService
    participant CU as CRUDUser
    participant SU as SecurityUtils
    participant DB as Database
    participant AL as AuditHelper

    C->>API: POST /api/v1/auth/login
    Note over API: {username, password}
    API->>API: 校验 Origin/Referer/Sec-Fetch-Site
    API->>AS: login_rate_limiter.hit(ip, identifier)
    alt 超出账户/IP 滑动窗口
        AS-->>API: retry_after
        API-->>C: 429 + Retry-After
    else 允许尝试
        API->>CU: authenticate(db, identifier, password)
        CU->>DB: SELECT user WHERE username/email=? AND is_deleted=false
        DB-->>CU: User | None
        Note over CU: rollback 释放连接，再做 KDF
        CU->>SU: verify_and_update_password(input, hashed)
        Note over SU: 线程池 + 并发闸门；<br/>未知用户也燃烧两种算法的 dummy hash
        SU-->>CU: PasswordVerification(valid, updated_hash)
        alt 密码错误或用户停用
            CU-->>API: None
            API->>AL: log(None, "login_failed", "auth", ip)
            AL->>DB: INSERT audit_logs; COMMIT
            API-->>C: 401 Unauthorized
        else 密码正确
            CU->>DB: SELECT user FOR NO KEY UPDATE（重读并加锁）
            opt 旧 bcrypt 哈希
                CU->>DB: UPDATE users SET hashed_password=<argon2id>
            end
            CU-->>API: User
            API->>AS: create_login_session(db, user)
            AS->>DB: SELECT user FOR NO KEY UPDATE
            AS->>SU: issue_refresh_token(user.id, ver)
            SU-->>AS: token + jti + family_id + expires_at
            AS->>DB: INSERT refresh_session_families
            AS->>DB: INSERT refresh_sessions(token_hash=HMAC(token))
            AS->>SU: create_access_token(user.id, ver, sid=family_id)
            SU-->>AS: access_token
            AS-->>API: SessionTokens
            API->>AL: log(user.id, "login", "auth", ip)
            AL->>DB: INSERT audit_logs
            API->>DB: COMMIT（业务写入与审计一次提交）
            API-->>C: 200 {access_token, token_type, expires_in}
            Note over API: Set-Cookie: refresh_token<br/>HttpOnly + SameSite=Strict + Path=/api/v1/auth
        end
    end
```

#### 4.2 权限校验流程

```mermaid
sequenceDiagram
    participant C as Client
    participant API as UsersAPI
    participant Dep as Dependencies
    participant SU as SecurityUtils
    participant AS as AuthService
    participant CU as CRUDUser
    participant DB as Database

    C->>API: GET /api/v1/users (Authorization: Bearer <token>)
    API->>Dep: require_permission("user:read")
    Dep->>SU: decode_token(access_token)
    alt Token 无效/过期/类型错误
        SU-->>Dep: JWTError
        Dep-->>API: 401 Unauthorized
        API-->>C: 401
    else Token 有效
        SU-->>Dep: TokenPayload {sub, ver, sid, type}
        Dep->>AS: get_authorized_session_user(user_id, sid, ver, "user:read")
        Note over AS: 会话有效性与权限判定合并为一条语句，<br/>每个受保护请求只需一次往返
        AS->>DB: SELECT users.*, EXISTS(权限子查询)<br/>JOIN refresh_session_families<br/>WHERE 账号可用 AND token_version 匹配<br/>AND family 未撤销且未过期
        DB-->>AS: (User, has_permission) | 无行
        alt 无行（会话被撤销 / 用户不可用 / 版本失效）
            AS-->>Dep: None
            Dep-->>API: 401 Unauthorized
            API-->>C: 401
        else 有行但 has_permission=false 且非超管
            AS-->>Dep: AuthorizedUser(has_permission=false)
            Dep-->>API: 403 Forbidden
            API-->>C: 403
        else 通过
            AS-->>Dep: AuthorizedUser(user, has_permission=true)
            Dep-->>API: current_user: User
            API->>CU: get_multi_filtered(db, ...)
            CU->>DB: SELECT count(*) + 分页查询<br/>WHERE is_deleted=false ORDER BY id LIMIT/OFFSET
            CU->>DB: selectinload 一次性加载各用户的启用角色
            DB-->>CU: [User, ...]
            CU-->>API: users list + total
            API-->>C: 200 {items, total, page, page_size}
        end
    end
```

#### 4.3 用户角色分配流程

```mermaid
sequenceDiagram
    participant C as Client
    participant API as UsersAPI
    participant Dep as Dependencies
    participant CU as CRUDUser
    participant CR as CRUDRole
    participant DB as Database
    participant AL as AuditHelper

    C->>API: PUT /api/v1/users/{id}/roles
    Note over API: {role_ids: [1, 2, 3]}
    API->>Dep: require_permission("user:assign")
    Dep-->>API: current_user (已验证)
    API->>CU: get(db, user_id)
    CU->>DB: SELECT * FROM users WHERE id=?
    DB-->>CU: User
    alt 用户不存在
        CU-->>API: None
        API-->>C: 404 Not Found
    else 用户存在
        CU-->>API: User
        loop 每个 role_id
            API->>CR: get(db, role_id)
            CR->>DB: SELECT * FROM roles WHERE id=? AND is_deleted=false
            DB-->>CR: Role | None
            alt 角色不存在
                CR-->>API: None
                API-->>C: 400 Bad Request {detail: "角色不存在"}
            end
        end
        API->>CU: assign_roles(db, user_id, role_ids)
        CU->>DB: DELETE FROM user_roles WHERE user_id=?
        CU->>DB: INSERT INTO user_roles (user_id, role_id) VALUES ...
        DB-->>CU: Success
        CU-->>API: User (with updated roles)
        API->>AL: log(db, current_user.id, "assign_roles",<br/>"user:{id}", "分配角色: [1,2,3]", ip)
        AL->>DB: INSERT INTO audit_logs
        API-->>C: 200 {user with roles}
    end
```

#### 4.4 Token 刷新流程

```mermaid
sequenceDiagram
    participant C as Client
    participant API as AuthAPI
    participant SU as SecurityUtils
    participant CU as CRUDUser
    participant DB as Database

    Note over C: access_token 过期，axios 拦截器捕获 401
    C->>API: POST /api/v1/auth/refresh
    Note over API: Cookie: refresh_token=xxx
    API->>SU: decode_token(refresh_token)
    alt refresh_token 无效/过期
        SU-->>API: JWTError
        API-->>C: 401 Unauthorized
        Note over API: Set-Cookie: refresh_token="" (清除)
    else refresh_token 有效
        SU-->>API: {sub, jti, sid, ver}
        API->>DB: SELECT user FOR NO KEY UPDATE
        API->>DB: SELECT family FOR UPDATE
        API->>DB: SELECT refresh_session FOR UPDATE
        alt 用户/会话无效，或旧 token 在有效期内重放
            API->>DB: UPDATE family SET revoked_at=now()
            API->>DB: INSERT audit_log; COMMIT
            API-->>C: 401 + clear cookie
        else 当前 token 可消费
            API->>SU: issue_refresh_token(user.id, family_id)
            SU-->>API: new_refresh_token
            API->>DB: 撤销旧 token，插入新摘要，延长 family，COMMIT
            API->>SU: create_access_token(user.id, ver, family_id)
            SU-->>API: new_access_token
            API-->>C: 200 {access_token, token_type}
            Note over API: Set-Cookie: new_refresh_token (HttpOnly)
        end
    end
```

#### 4.5 用户创建流程（初始化）

```mermaid
sequenceDiagram
    participant C as Client
    participant API as UsersAPI
    participant Dep as Dependencies
    participant CU as CRUDUser
    participant SU as SecurityUtils
    participant DB as Database
    participant AL as AuditHelper

    C->>API: POST /api/v1/users
    Note over API: {username, email, password, nickname, role_ids}
    API->>Dep: require_permission("user:create")
    Dep-->>API: current_user (已验证)
    API->>CU: get_by_username(db, username)
    CU->>DB: SELECT * FROM users WHERE username=?
    DB-->>CU: None
    API->>CU: get_by_email(db, email)
    CU->>DB: SELECT * FROM users WHERE email=?
    DB-->>CU: None
    API->>SU: hash_password(password)
    SU-->>API: hashed_password
    API->>CU: create(db, {username, email, hashed_password, ...})
    CU->>DB: INSERT INTO users ...
    DB-->>CU: User (with id)
    API->>CU: assign_roles(db, user.id, role_ids)
    CU->>DB: INSERT INTO user_roles ...
    DB-->>CU: User (with roles)
    CU-->>API: User
    API->>AL: log(db, current_user.id, "create_user",<br/>"user:{id}", "创建用户: {username}", ip)
    AL->>DB: INSERT INTO audit_logs
    API-->>C: 201 {user}
```

---

### 5. 已决事项与部署约束

| # | 问题 | 当前假设 | 风险/影响 |
|---|------|----------|-----------|
| U1 | **Python 3.14 + psycopg v3 兼容性** | 已在 Python 3.14.3 验证。运行时异步；Windows 使用 Selector loop；Alembic 使用同步连接 | 已解决；生产推荐 Linux，Windows 必须通过 `main.py` 启动 |
| U2 | **密码哈希兼容性** | 新密码固定 Argon2id；旧 bcrypt（包括历史 72-byte 截断密码）可验证并迁移完整密码 | 已解决；保留 bcrypt 依赖仅用于旧数据与等成本验证 |
| U3 | **refresh_token 轮换的服务端存储** | `refresh_session_families` 是整族锁与撤销真源，`refresh_sessions` 只存 token 摘要和轮换历史 | 已解决；部署前必须执行 Alembic 到 head |
| U4 | **前端构建产物部署路径** | 假设 Nginx 独立部署前端静态文件，API 通过 Nginx 反代到后端 8000 端口。具体的 Nginx 配置不在本次架构设计范围内 | 低 — 部署阶段处理 |
| U5 | **初始超级管理员创建** | 通过一次性 `init_db.py` 创建；必须显式传入凭据；已有任意超级管理员或标识冲突时失败，不提升现有账户 | 已解决；脚本使用事务锁并写入审计日志 |
| U6 | **前端 shadcn 组件版本兼容性** | shadcn 使用 `base-luma` style + `hugeicons` 图标库，部分组件 API 可能与标准 shadcn 有差异。工程师在添加组件时需注意 | 低 — 按需调整 |

---

## Part B: 任务分解

### 6. 依赖包列表

#### 6.1 后端依赖（`uv add`）

**生产依赖：**

```bash
cd backend
uv add fastapi
uv add "uvicorn[standard]"
uv add "sqlalchemy>=2.0"
uv add "psycopg[binary]>=3.2"
uv add alembic
uv add pydantic-settings
uv add "pydantic[email]"
uv add PyJWT
uv add "pwdlib[argon2,bcrypt]"
uv add python-multipart
```

| 包名 | 用途 |
|------|------|
| fastapi | Web 框架，路由 + 依赖注入 |
| uvicorn[standard] | ASGI 服务器，运行 FastAPI |
| sqlalchemy>=2.0 | ORM，2.0 新 API 类型安全 |
| psycopg[binary]>=3.2 | PostgreSQL 驱动 v3，含预编译二进制 |
| alembic | 数据库迁移管理 |
| pydantic-settings | 从 .env 读取配置，类型安全 |
| pydantic[email] | `EmailStr` 的显式、可锁定邮箱校验依赖 |
| PyJWT | JWT 签发与标准声明验证 |
| pwdlib[argon2,bcrypt] | Argon2id 新哈希与旧 bcrypt 迁移 |
| python-multipart | OAuth2PasswordRequestForm 表单解析 |

**开发依赖：**

```bash
uv add --dev ruff
uv add --dev mypy
uv add --dev pytest
uv add --dev pytest-asyncio
uv add --dev aiosqlite
uv add --dev httpx
```

| 包名 | 用途 |
|------|------|
| ruff | 代码 lint + 格式化 |
| mypy | 静态类型检查 |
| pytest | 单元测试框架 |
| pytest-asyncio | 异步测试与 fixture 支持 |
| aiosqlite | 快速单元测试的异步 SQLite 驱动 |
| httpx | `AsyncClient` + ASGI transport，测试 HTTP 请求 |

#### 6.2 前端依赖（`npm install`）

```bash
cd frontend
npm install react-router
npm install zustand
npm install axios
npm install react-hook-form
npm install @hookform/resolvers
npm install zod
npm install dayjs
npm install @tanstack/react-table
```

| 包名 | 用途 |
|------|------|
| react-router | 路由管理（v7 合并了 dom 包） |
| zustand | 全局状态管理（auth store） |
| axios | HTTP 客户端 + 拦截器（JWT 携带、401 刷新） |
| react-hook-form | 表单状态管理（非受控，高性能） |
| @hookform/resolvers | react-hook-form 与 zod 的桥接 |
| zod | Schema 验证 + TypeScript 类型推导 |
| dayjs | 日期格式化（轻量替代 moment.js） |
| @tanstack/react-table | Headless 数据表格引擎 |

> **注意**: react, react-dom, shadcn, tailwindcss, class-variance-authority, clsx, tailwind-merge, @base-ui/react, @hugeicons/react 等已安装，无需重复安装。

#### 6.3 shadcn 组件清单

通过 `npx shadcn add` 添加以下组件（在 T04 任务中执行）：

```bash
cd frontend
npx shadcn add card input label form dialog alert-dialog dropdown-menu select checkbox table badge avatar sheet breadcrumb pagination skeleton sonner tabs separator scroll-area progress tooltip sidebar
```

| 组件 | 用途 |
|------|------|
| card | 卡片容器（登录、仪表盘、表单） |
| input | 输入框 |
| label | 表单标签 |
| form | 表单布局（配合 react-hook-form） |
| dialog | 模态对话框（新增/编辑） |
| alert-dialog | 二次确认对话框（删除） |
| dropdown-menu | 下拉菜单（操作列、用户菜单） |
| select | 下拉选择（筛选、模块选择） |
| checkbox | 复选框（角色/权限多选） |
| table | 数据表格 |
| badge | 状态标签 |
| avatar | 用户头像 |
| sheet | 抽屉（移动端侧边栏） |
| breadcrumb | 面包屑导航 |
| pagination | 分页导航 |
| skeleton | 骨架屏加载 |
| sonner | Toast 通知 |
| tabs | 标签页切换 |
| separator | 分隔线 |
| scroll-area | 滚动区域 |
| progress | 进度条（密码强度） |
| tooltip | 悬浮提示 |
| sidebar | 侧边栏组件（shadcn 内置 sidebar） |

---

### 7. 任务列表

> **约束**: 最多 5 个任务，每个任务 ≥ 3 个文件，按功能模块/层次分组。

---

#### T01: 项目基础设施（后端 + 前端配置、入口、环境变量）

| 项目 | 内容 |
|------|------|
| **优先级** | P0 |
| **依赖** | 无 |
| **目标** | 搭建后端 FastAPI 骨架 + 前端路由骨架 + 全局配置 + .gitignore，使项目可启动 |

**涉及文件（10 个）：**

| # | 文件 | 做什么 |
|---|------|--------|
| 1 | `backend/pyproject.toml` | 添加全部后端依赖（生产 + 开发），配置 ruff/mypy 规则 |
| 2 | `backend/main.py` | 改为 uvicorn 启动入口：`uvicorn.run("app.main:app", ...)` |
| 3 | `backend/.env.example` | 环境变量模板（DATABASE_URL, SECRET_KEY, CORS 等） |
| 4 | `backend/app/__init__.py` | 空包初始化 |
| 5 | `backend/app/main.py` | FastAPI 应用实例、CORS 中间件、路由注册、全局异常处理 |
| 6 | `backend/app/core/__init__.py` | 空包初始化 |
| 7 | `backend/app/core/config.py` | Pydantic Settings 配置类，读取 .env |
| 8 | `frontend/.env.example` | `VITE_API_BASE_URL=http://localhost:8000/api/v1` |
| 9 | `frontend/src/lib/constants.ts` | 路由路径常量、权限码常量、localStorage key |
| 10 | `.gitignore` | 根目录 Git 忽略规则（只跟踪源代码） |

**验收标准：**
- `cd backend && uv run python main.py` 可启动，非生产环境访问 `/docs` 看到 Swagger UI
- 前端 `npm run dev` 可启动（App.tsx 暂时显示占位内容）
- `.gitignore` 只排除密钥、缓存和构建产物；`tests/`、`docs/` 必须纳入版本控制

---

#### T02: 后端数据模型层（models + schemas + database + security）

| 项目 | 内容 |
|------|------|
| **优先级** | P0 |
| **依赖** | T01 |
| **目标** | 定义全部 SQLAlchemy 模型、Pydantic Schema、数据库连接、安全工具 |

**涉及文件（15 个）：**

| # | 文件 | 做什么 |
|---|------|--------|
| 1 | `backend/app/core/database.py` | SQLAlchemy AsyncEngine（默认 pool_size=5, max_overflow=5）、AsyncSessionLocal、异步 get_db |
| 2 | `backend/app/core/security.py` | Argon2id/旧 bcrypt 等成本验证、JWT access/refresh token 签发与解码 |
| 3 | `backend/app/models/__init__.py` | 导出所有模型，供 Alembic autogenerate 使用 |
| 4 | `backend/app/models/base.py` | Base 声明类 + TimestampMixin（created_at, updated_at） |
| 5 | `backend/app/models/user.py` | User 模型 + UserRole 关联表 |
| 6 | `backend/app/models/role.py` | Role 模型 + RolePermission 关联表 |
| 7 | `backend/app/models/permission.py` | Permission 模型 |
| 8 | `backend/app/models/audit_log.py` | AuditLog 模型 |
| 9 | `backend/app/schemas/__init__.py` | 空包初始化 |
| 10 | `backend/app/schemas/common.py` | PaginationParams、PaginatedResponse[T]、ResponseEnvelope[T] |
| 11 | `backend/app/schemas/auth.py` | UserRegister, UserLogin, TokenPair, TokenPayload |
| 12 | `backend/app/schemas/user.py` | UserCreate, UserUpdate, UserResponse, UserWithRoles, AssignRoles |
| 13 | `backend/app/schemas/role.py` | RoleCreate, RoleUpdate, RoleResponse, RoleWithPermissions, AssignPermissions |
| 14 | `backend/app/schemas/permission.py` | PermissionCreate, PermissionUpdate, PermissionResponse |
| 15 | `backend/app/schemas/audit_log.py` + `backend/app/schemas/dashboard.py` | AuditLogResponse, DashboardStats（合并为一个文件组） |

**验收标准：**
- 所有模型可被 Alembic autogenerate 正确识别
- `mypy` 类型检查通过
- `ruff check` 无报错
- SecurityUtils 可正确签发/解码 JWT

---

#### T03: 后端业务逻辑层（crud + api routes + deps + utils + alembic + tests）

| 项目 | 内容 |
|------|------|
| **优先级** | P0 |
| **依赖** | T02 |
| **目标** | 实现全部 CRUD、API 路由（23 个端点）、依赖注入、审计工具、Alembic 迁移、测试 |

**涉及文件（24 个）：**

| # | 文件 | 做什么 |
|---|------|--------|
| 1 | `backend/app/core/deps.py` | get_db, get_current_user（JWT 解析）, require_permission（权限校验工厂）, get_current_admin |
| 2 | `backend/app/crud/__init__.py` | 导出 CRUD 实例（user, role, permission, audit_log） |
| 3 | `backend/app/crud/base.py` | CRUDBase 泛型基类（create, get, get_multi, update, soft_delete） |
| 4 | `backend/app/crud/user.py` | 用户 CRUD：authenticate, get_by_username/email, get_multi_filtered, assign_roles, get_permission_codes |
| 5 | `backend/app/crud/role.py` | 角色 CRUD：get_by_name, assign_permissions, get_user_count |
| 6 | `backend/app/crud/permission.py` | 权限 CRUD：get_by_code, get_by_module, get_all_grouped |
| 7 | `backend/app/crud/audit_log.py` | 审计日志 CRUD：create, get_multi_filtered |
| 8 | `backend/app/utils/__init__.py` | 空包初始化 |
| 9 | `backend/app/utils/audit.py` | log_audit() 工具函数 |
| 10 | `backend/app/api/__init__.py` | 空包初始化 |
| 11 | `backend/app/api/router.py` | 聚合 v1 所有子路由 |
| 12 | `backend/app/api/v1/__init__.py` | 空包初始化 |
| 13 | `backend/app/api/v1/auth.py` | register, login, refresh, logout（4 端点） |
| 14 | `backend/app/api/v1/users.py` | list, create, get, update, delete, assign_roles（6 端点） |
| 15 | `backend/app/api/v1/roles.py` | list, create, update, delete, assign_permissions（5 端点） |
| 16 | `backend/app/api/v1/permissions.py` | list, create, update, delete（4 端点） |
| 17 | `backend/app/api/v1/me.py` | get_profile, update_profile, change_password（3 端点） |
| 18 | `backend/app/api/v1/dashboard.py` | dashboard stats（1 端点） |
| 19 | `backend/app/api/v1/audit_logs.py` | list audit logs（1 端点） |
| 20 | `backend/alembic.ini` | Alembic 配置 |
| 21 | `backend/alembic/env.py` | Alembic 环境（导入所有模型，支持 autogenerate） |
| 22 | `backend/alembic/script.py.mako` + `backend/alembic/versions/.gitkeep` | 迁移模板 + 版本目录 |
| 23 | `backend/tests/conftest.py` | pytest fixtures：测试数据库、TestClient、认证 fixture |
| 24 | `backend/tests/test_*.py`（5 个测试文件） | test_auth, test_users, test_roles, test_permissions, test_audit |

**验收标准：**
- `alembic upgrade head` 可创建全部表
- `alembic revision --autogenerate -m "init"` 生成的迁移脚本正确
- 全部 23 个 API 端点可通过 Swagger UI 测试
- `pytest` 全绿
- `ruff check && mypy app/` 无报错

---

#### T04: 前端基础架构层（types + lib/api + store + hooks + layout + common 组件 + shadcn 组件安装）

| 项目 | 内容 |
|------|------|
| **优先级** | P0 |
| **依赖** | T01 |
| **目标** | 搭建前端类型系统、API 客户端、状态管理、路由守卫、布局框架、通用组件 |

**涉及文件（19 个）：**

| # | 文件 | 做什么 |
|---|------|--------|
| 1 | `frontend/src/types/api.ts` | ApiResponse<T>, PaginatedResponse<T>, ApiError |
| 2 | `frontend/src/types/auth.ts` | LoginRequest, TokenResponse, UserInfo |
| 3 | `frontend/src/types/user.ts` | User, UserCreate, UserUpdate, UserWithRoles |
| 4 | `frontend/src/types/role.ts` | Role, RoleCreate, RoleUpdate, RoleWithPermissions |
| 5 | `frontend/src/types/permission.ts` | Permission, PermissionCreate, PermissionUpdate |
| 6 | `frontend/src/types/audit.ts` | AuditLog, AuditLogQueryParams |
| 7 | `frontend/src/types/index.ts` | 统一导出 |
| 8 | `frontend/src/lib/api.ts` | Axios 实例：请求拦截器（携带 access_token）、响应拦截器（401 自动刷新） |
| 9 | `frontend/src/store/auth.ts` | Zustand store：token, user, permissions, login(), logout(), refresh() |
| 10 | `frontend/src/hooks/use-auth.ts` | 封装 auth store + API 调用（login, logout, fetchProfile） |
| 11 | `frontend/src/hooks/use-permission.ts` | hasPermission(code) 校验 hook |
| 12 | `frontend/src/components/layout/AppLayout.tsx` | 主布局：Sidebar + Header + Outlet |
| 13 | `frontend/src/components/layout/Sidebar.tsx` | 侧边导航（响应式：桌面固定，移动端 Sheet 抽屉） |
| 14 | `frontend/src/components/layout/Header.tsx` | 顶部栏：面包屑 + 用户下拉菜单 + 主题切换 |
| 15 | `frontend/src/components/layout/PageHeader.tsx` | 页面标题 + 操作按钮区 |
| 16 | `frontend/src/components/auth/ProtectedRoute.tsx` | 路由守卫：未登录→/login，无权限→/403 |
| 17 | `frontend/src/components/common/DataTable.tsx` | TanStack Table + shadcn Table 通用组件 |
| 18 | `frontend/src/components/common/Pagination.tsx` | 分页组件（页码 + 每页条数） |
| 19 | `frontend/src/components/common/ConfirmDialog.tsx` + `ErrorBoundary.tsx` | 删除确认 + 错误边界 |

**额外操作（非文件创建）：**
- 执行 `npx shadcn add card input label form dialog alert-dialog dropdown-menu select checkbox table badge avatar sheet breadcrumb pagination skeleton sonner tabs separator scroll-area progress tooltip sidebar`
- 执行 `npm install react-router zustand axios react-hook-form @hookform/resolvers zod dayjs @tanstack/react-table`

**验收标准：**
- `npm run typecheck` 无报错
- AppLayout 可正确渲染侧边栏 + 顶栏
- ProtectedRoute 可拦截未认证访问
- Axios 拦截器正确携带 token 并处理 401
- Zustand store 正确管理 auth 状态

---

#### T05: 前端页面层（全部页面 + 业务组件 + 路由配置）

| 项目 | 内容 |
|------|------|
| **优先级** | P0 |
| **依赖** | T04 |
| **目标** | 实现全部 9 个页面 + 4 个业务对话框组件 + 路由配置，前端功能完整可用 |

**涉及文件（14 个）：**

| # | 文件 | 做什么 |
|---|------|--------|
| 1 | `frontend/src/App.tsx` | 路由定义：Login / AppLayout(ProtectedRoute) → Dashboard/Users/Roles/Permissions/Profile/AuditLogs / 403 / 404 |
| 2 | `frontend/src/main.tsx` | 更新入口：BrowserRouter + ThemeProvider + App + Sonner（Toast） |
| 3 | `frontend/src/pages/LoginPage.tsx` | 登录页：表单（react-hook-form + zod）+ 品牌区 + 响应式 |
| 4 | `frontend/src/pages/DashboardPage.tsx` | 仪表盘：统计卡片 + 最近登录 + 快捷操作 |
| 5 | `frontend/src/pages/UsersPage.tsx` | 用户管理：DataTable + 搜索/筛选 + 新增/编辑/删除/角色分配 |
| 6 | `frontend/src/pages/RolesPage.tsx` | 角色管理：DataTable + 新增/编辑/删除/权限分配 |
| 7 | `frontend/src/pages/PermissionsPage.tsx` | 权限管理：按模块分组展示 + 新增/编辑/删除 |
| 8 | `frontend/src/pages/ProfilePage.tsx` | 个人中心：信息编辑 + 修改密码 |
| 9 | `frontend/src/pages/AuditLogsPage.tsx` | 审计日志：DataTable + 筛选 |
| 10 | `frontend/src/pages/ForbiddenPage.tsx` | 403 页面 |
| 11 | `frontend/src/pages/NotFoundPage.tsx` | 404 页面 |
| 12 | `frontend/src/components/users/UserFormDialog.tsx` | 用户新增/编辑表单 Dialog |
| 13 | `frontend/src/components/users/AssignRolesDialog.tsx` | 用户角色分配 Dialog |
| 14 | `frontend/src/components/roles/RoleFormDialog.tsx` + `AssignPermissionsDialog.tsx` | 角色表单 + 权限分配 Dialog |

**验收标准：**
- `npm run build` 构建成功
- `npm run typecheck` 无报错
- `npm run lint` 无报错
- 登录→仪表盘→用户/角色/权限管理 全流程可走通
- 响应式布局在移动端正常（侧边栏抽屉）
- 路由守卫正确拦截

---

### 8. 共享知识

#### 8.1 后端编码规范

```
- Python 3.14.3，严格使用类型注解（mypy strict 模式）
- 分层架构：models → schemas → crud → api，禁止跨层调用（如 api 直接操作 model）
- 所有 API 路径前缀：/api/v1/
- 所有 ORM 模型继承 Base + TimestampMixin
- 软删除：is_deleted=True 表示已删除，查询时统一过滤
- 密码哈希：新数据 Argon2id；旧 bcrypt 仅验证并在成功登录后迁移；CPU/内存型工作通过有界线程闸门执行
- JWT：HS256，access token 默认 30min，refresh token 默认 7 天；refresh 原文不入库
- Token payload 至少包含 sub/exp/iat/iss/aud/jti/type/ver/sid；服务端同时校验 token version 与 family 状态
- 统一响应格式：{"code": 200, "data": T, "message": "success"}
- 分页响应格式：{"code": 200, "data": {"items": [...], "total": 100, "page": 1, "page_size": 20}, "message": "success"}
- 数据库 AsyncSession 通过 Depends(get_db) 注入；CRUD 只 flush，路由在业务与审计均成功后单次 commit
- 权限校验通过 Depends(require_permission("xxx")) 注入
- 审计日志：在 API 路由层调用 utils.audit.log_audit() 记录
- 所有日期时间存储为 UTC，使用 datetime.now(timezone.utc)
- .env 文件不提交 git，仅提交 .env.example
```

#### 8.2 前端编码规范

```
- TypeScript strict 模式，所有变量/函数/组件需有类型注解
- 路径别名：@/ → ./src/（已在 vite.config.ts 和 tsconfig 中配置）
- API 响应统一通过 lib/api.ts 的 axios 实例发送，自动携带 JWT
- access_token 存储在 zustand store（内存中），不持久化到 localStorage
- refresh_token 由后端通过 httpOnly cookie 管理，前端不直接操作
- 401 响应时 axios 拦截器自动调用 /auth/refresh，失败则跳转 /login
- 页面组件命名：XxxPage.tsx，放在 src/pages/
- 业务组件命名：XxxDialog.tsx / XxxForm.tsx，放在 src/components/{module}/
- 通用组件放在 src/components/common/
- shadcn UI 组件放在 src/components/ui/（通过 npx shadcn add 添加）
- 表单使用 react-hook-form + zod 验证
- 数据表格使用 @tanstack/react-table + shadcn Table
- 日期格式化使用 dayjs，统一格式 "YYYY-MM-DD HH:mm:ss"
- 路由守卫：ProtectedRoute 组件包裹需要认证的路由
- 权限码格式：module:action（如 user:read, role:create）
- 前端权限控制：usePermission hook 检查当前用户权限码列表
```

#### 8.3 安全规范

```
- 密码长度：8–128 字符；新密码使用 Argon2id，旧 bcrypt 只用于兼容迁移
- 密码哈希并发和排队时间有上限，过载返回 503
- JWT SECRET_KEY：至少 32 字符随机字符串
- CORS：生产环境严格白名单，开发环境允许 localhost
- refresh_token cookie 属性：HttpOnly, Secure(生产), SameSite=Strict, Path=/api/v1/auth
- 所有敏感操作（创建/删除/分配）记录审计日志
- SQL 注入防护：SQLAlchemy 参数化查询，禁止拼接 SQL
- XSS 防护：React 默认转义，不使用 dangerouslySetInnerHTML
- CSRF 防护：SameSite=Strict + login/register/refresh/logout 来源校验；API 业务认证使用 Bearer token
- 代理头只由应用内 ProxyHeadersMiddleware 按 TRUSTED_PROXY_CIDRS 解析；外层 Uvicorn 必须关闭自己的 proxy headers
```

#### 8.4 数据库约定

```
- 主键：自增 int id
- 时间字段：created_at（创建时自动填充）、updated_at（更新时自动填充）
- 软删除字段：is_deleted（默认 False），is_active（默认 True，用于启用/禁用）
- 关联表（UserRole, RolePermission）：只有外键 + created_at，无 id
- 表名：蛇形命名（users, roles, permissions, user_roles, role_permissions, audit_logs）
- 字段名：蛇形命名（hashed_password, is_active, created_at）
- 外键约束：ON DELETE CASCADE（删除用户时级联删除关联记录）
- 索引：username, email, permission.code 唯一索引；is_deleted 普通索引
```

#### 8.5 环境变量

**后端 `.env`：**
```
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/fastapi_admin
SECRET_KEY=your-secret-key-at-least-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=5
BACKEND_CORS_ORIGINS=http://localhost:5173,http://localhost:3000
COOKIE_SECURE=false
```

**前端 `.env`：**
```
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

---

### 9. 任务依赖图

```mermaid
graph TD
    T01[T01: 项目基础设施<br/>后端配置+前端配置+入口+.gitignore<br/>10 个文件]
    T02[T02: 后端数据模型层<br/>models + schemas + database + security<br/>15 个文件]
    T03[T03: 后端业务逻辑层<br/>crud + api + deps + utils + alembic + tests<br/>24 个文件]
    T04[T04: 前端基础架构层<br/>types + lib/api + store + hooks + layout + common<br/>19 个文件]
    T05[T05: 前端页面层<br/>全部页面 + 业务组件 + 路由配置<br/>14 个文件]

    T01 --> T02
    T01 --> T04
    T02 --> T03
    T04 --> T05

    style T01 fill:#4ade80,stroke:#16a34a,color:#000
    style T02 fill:#60a5fa,stroke:#2563eb,color:#000
    style T03 fill:#60a5fa,stroke:#2563eb,color:#000
    style T04 fill:#f59e0b,stroke:#d97706,color:#000
    style T05 fill:#f59e0b,stroke:#d97706,color:#000
```

**并行说明：**
- T01 完成后，T02（后端）和 T04（前端）可**并行开发**
- T03 依赖 T02（需要模型和 Schema 定义）
- T05 依赖 T04（需要类型、API 客户端、布局组件）
- 理想执行路径：T01 → (T02 ∥ T04) → (T03 ∥ T05)

**任务统计：**

| 任务 | 文件数 | 优先级 | 依赖 |
|------|--------|--------|------|
| T01 | 10 | P0 | 无 |
| T02 | 15 | P0 | T01 |
| T03 | 24 | P0 | T02 |
| T04 | 19 | P0 | T01 |
| T05 | 14 | P0 | T04 |
| **合计** | **82** | | |

> 注：文件总数 91（含已存在但需修改的文件），任务覆盖 82 个新增/修改文件，其余为已存在且无需修改的文件（如 components/ui/button.tsx, theme-provider.tsx, lib/utils.ts, index.css, tsconfig 等）。

---

> **文档结束**
> 如有疑问，请联系架构师 李剑桥。
