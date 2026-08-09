# 权限管理系统 PRD

> **项目名称**: fastapi-admin  
> **文档版本**: v1.0  
> **撰写人**: 李剑桥 
> **日期**: 2025-08-07  

---

## 1. 项目信息

| 项目 | 内容 |
|------|------|
| **项目名称** | fastapi-admin |
| **项目类型** | 全栈 Web 应用（权限管理系统） |
| **语言** | 中文 |
| **编程语言** | Python 3.14.3 / TypeScript |
| **后端技术栈** | FastAPI + SQLAlchemy + PostgreSQL + JWT |
| **前端技术栈** | React 19 + TypeScript + shadcn/UI + Tailwind CSS + Vite |
| **依赖管理** | uv（后端）/ npm（前端） |
| **代码质量** | ruff + mypy + pytest（全绿） |

### 原始需求复述

用户李剑桥（资深运维专家）需要一个完整的权限管理系统，类似 Django admin，包含：用户管理、角色管理、权限管理、用户角色分配、接口权限控制五大核心模块。系统采用前后端分离架构，后端基于 FastAPI + SQLAlchemy + PostgreSQL + JWT，前端基于 React 19 + shadcn/UI，实现响应式布局，支持移动端访问。

---

## 2. 产品定义

### 2.1 产品目标

| # | 目标 | 描述 | 衡量指标 |
|---|------|------|----------|
| G1 | **精细化权限管控** | 提供基于 RBAC（角色-权限）模型的细粒度权限管理，支持 API 端点级别的访问控制 | 100% API 端点受权限保护；权限粒度可到单个操作（增/删/改/查） |
| G2 | **开箱即用的管理后台** | 提供完整的可视化管理界面，零配置即可完成用户/角色/权限的全生命周期管理 | 核心页面 5 个（登录/用户/角色/权限/仪表盘）；3 步内完成任意管理操作 |
| G3 | **安全合规基线** | 遵循行业安全标准，密码哈希存储、JWT 鉴权、HTTPS 支持、防 CSRF/XSS | OWASP Top 10 基本覆盖；新密码使用 Argon2id；JWT 合理过期且会话可撤销 |

### 2.2 用户故事

| # | 角色 | 场景 | 价值 |
|---|------|------|------|
| US1 | 系统管理员 | 我希望能注册和登录系统 | 以便安全地访问管理后台 |
| US2 | 系统管理员 | 我希望能查看、搜索、新增、编辑、禁用用户 | 以便管理系统中所有用户的生命周期 |
| US3 | 系统管理员 | 我希望能创建、编辑、删除角色 | 以便按业务场景灵活定义角色集合 |
| US4 | 系统管理员 | 我希望能定义权限项，并将权限分配给角色 | 以便精确控制每个角色可执行的操作 |
| US5 | 系统管理员 | 我希望能为用户分配一个或多个角色 | 以便灵活组合用户权限，支持一人多角色 |
| US6 | 系统管理员 | 我希望通过仪表盘查看系统概览（用户数、角色数、权限数、最近登录） | 以便快速了解系统运行状态 |
| US7 | 普通用户 | 我希望能登录后查看和修改自己的个人信息和密码 | 以便维护个人账户安全 |

---

## 3. 技术规范

### 3.1 需求池

#### P0 — 必须有（MVP 核心功能）

| ID | 模块 | 需求描述 | 验收标准 |
|----|------|----------|----------|
| P0-01 | 认证 | 用户注册接口 | 邮箱+用户名+密码注册；新密码使用 Argon2id 哈希；邮箱/用户名唯一约束；默认关闭自助注册，启用时限流 |
| P0-02 | 认证 | 用户登录接口（JWT 签发） | 账号密码校验通过后签发 access_token + refresh_token；access_token 过期时间 ≤ 30min |
| P0-03 | 认证 | JWT 中间件（依赖注入） | 所有受保护端点通过 `Depends(get_current_user)` 注入当前用户；token 过期/无效返回 401 |
| P0-04 | 认证 | Token 刷新接口 | refresh_token 有效时签发新 access_token；服务端持久化会话族并原子轮换；有效期内的已消费 token 重放时撤销整个会话族 |
| P0-05 | 用户管理 | 用户 CRUD | 新增/查询（列表+详情）/更新/删除（软删除）；列表支持分页、搜索、筛选 |
| P0-06 | 角色管理 | 角色 CRUD | 新增/查询/更新/删除；角色名唯一；删除前校验是否有用户关联 |
| P0-07 | 权限管理 | 权限 CRUD | 新增/查询/更新/删除；权限标识唯一（如 `user:read`）；权限含名称、标识、描述、模块归属 |
| P0-08 | 用户角色 | 用户-角色分配 | 支持为用户分配多个角色；支持查看用户所有角色；支持移除角色 |
| P0-09 | 权限分配 | 角色-权限分配 | 支持为角色分配多个权限；支持查看角色所有权限；支持移除权限 |
| P0-10 | 权限控制 | API 端点权限校验 | 提供权限装饰器/依赖注入 `require_permission("xxx")`；无权限返回 403 |
| P0-11 | 安全 | 密码安全哈希存储 | 新密码使用 Argon2id；旧 bcrypt 哈希可验证并在成功登录后迁移；哈希工作不得阻塞事件循环 |
| P0-12 | 前端 | 登录页 | 表单（用户名/邮箱 + 密码）；表单校验；登录失败提示；登录成功跳转仪表盘 |
| P0-13 | 前端 | 用户管理页 | 数据表格（shadcn Table）；分页；搜索框；新增/编辑 Dialog；删除确认；角色分配 Dialog |
| P0-14 | 前端 | 角色管理页 | 数据表格；新增/编辑 Dialog（含权限分配多选）；删除确认 |
| P0-15 | 前端 | 权限管理页 | 数据表格；新增/编辑 Dialog；删除确认；按模块分组展示 |
| P0-16 | 前端 | 布局框架 | 侧边栏导航 + 顶部栏（用户信息+退出） + 主内容区；响应式（移动端侧边栏收起为抽屉） |
| P0-17 | 前端 | 路由守卫 | 未登录跳转登录页；无权限页面显示 403 提示 |
| P0-18 | 前端 | API 请求封装 | axios/fetch 封装；自动携带 JWT；401 自动跳转登录；token 刷新拦截器 |

#### P1 — 应该有（增强体验与安全）

| ID | 模块 | 需求描述 | 验收标准 |
|----|------|----------|----------|
| P1-01 | 用户管理 | 用户启用/禁用 | 禁用用户无法登录；禁用状态在列表标识 |
| P1-02 | 用户管理 | 批量操作 | 批量启用/禁用/删除用户 |
| P1-03 | 用户管理 | 个人信息管理 | 用户可修改自己的昵称、邮箱；不可修改用户名 |
| P1-04 | 用户管理 | 修改密码 | 需验证旧密码；新密码使用 Argon2id；修改后撤销该用户全部现有会话 |
| P1-05 | 角色管理 | 角色继承（可选简化） | 角色可继承父角色的权限（若实现复杂度高则降级为 P2） |
| P1-06 | 前端 | 仪表盘页 | 统计卡片（用户数/角色数/权限数）；最近登录用户列表；快捷操作入口 |
| P1-07 | 前端 | 深色/浅色主题切换 | shadcn 主题支持；偏好持久化到 localStorage |
| P1-08 | 安全 | 接口限流 | 登录按账户+IP、账户总量及 IP 总量限流；注册限流；多实例生产环境在共享网关再次限流 |
| P1-09 | 安全 | CORS 配置 | 白名单域名；生产环境严格限制 |
| P1-10 | 审计 | 操作日志 | 记录关键操作（登录/用户变更/角色变更/权限变更）；含操作人、时间、IP、操作内容 |
| P1-11 | 前端 | 加载状态与错误提示 | 全局 loading 骨架屏；统一的错误 Toast 提示 |
| P1-12 | 后端 | 数据库迁移 | 使用 Alembic 管理数据库 schema 变更 |

#### P2 — 可以有（锦上添花）

| ID | 模块 | 需求描述 | 验收标准 |
|----|------|----------|----------|
| P2-01 | 认证 | OAuth2 第三方登录 | 支持 GitHub/Google 登录（预留接口） |
| P2-02 | 用户管理 | 用户头像上传 | 支持上传头像；存储到本地/对象存储 |
| P2-03 | 权限管理 | 权限导入/导出 | JSON 格式批量导入/导出权限定义 |
| P2-04 | 前端 | 国际化 i18n | 支持中/英文切换 |
| P2-05 | 前端 | 数据导出 | 用户/角色列表导出 CSV |
| P2-06 | 运维 | Docker 部署 | 提供 docker-compose.yml 一键启动 |
| P2-07 | 运维 | CI/CD 流水线 | GitHub Actions 自动测试+构建 |
| P2-08 | 体验 | 登录页验证码 | 连续失败后触发图形验证码 |
| P2-09 | 安全 | HTTPS 自动化 | 集成 Let's Encrypt 自动证书 |
| P2-10 | 审计 | 操作日志可视化 | 审计日志列表页 + 时间线视图 |

---

### 3.2 UI 设计稿要点

#### 页面总览

| 页面 | 路由 | P 级 | 说明 |
|------|------|------|------|
| 登录页 | `/login` | P0 | 系统入口 |
| 仪表盘 | `/` | P1 | 运营概览 |
| 用户管理 | `/users` | P0 | 用户生命周期管理 |
| 角色管理 | `/roles` | P0 | 角色与权限分配 |
| 权限管理 | `/permissions` | P0 | 权限项定义 |
| 个人中心 | `/profile` | P1 | 个人信息与密码 |
| 操作日志 | `/audit` | P1 | 审计日志查看 |
| 403 页面 | `/403` | P0 | 无权限提示 |
| 404 页面 | `*` | P0 | 路由兜底 |

---

#### 页面 1：登录页 `/login`

**布局结构**：全屏居中布局，左右分栏（桌面端）/ 单列（移动端）

**组件构成**：
- **左侧品牌区**（桌面端 50% 宽）：系统名称、Logo、简短 slogan、装饰性背景
- **右侧表单区**（桌面端 50% 宽，移动端 100%）：
  - shadcn `Card` 容器
  - `CardHeader`：标题「登录」+ 副标题
  - `CardContent` → `Form`：
    - `FormField` + `Input`：用户名/邮箱
    - `FormField` + `Input[type=password]`：密码
    - `FormField` + `Checkbox`：记住我
  - `CardFooter` → `Button`：登录（full width）
  - 底部链接：注册账号（如启用注册）、忘记密码（P2）

**交互要点**：
- 表单校验：非空、邮箱格式、密码长度 ≥ 8
- 登录中：Button 显示 loading spinner
- 登录失败：Toast 错误提示
- 登录成功：跳转仪表盘，Token 存入 localStorage/sessionStorage

---

#### 页面 2：仪表盘 `/`（P1）

**布局结构**：主内容区内网格布局

**组件构成**：
- 顶部：`PageHeader`（页面标题「仪表盘」+ 当前时间/欢迎语）
- 统计卡片区（`grid grid-cols-1 md:grid-cols-4 gap-4`）：
  - 4 × `Card`：用户总数、角色总数、权限总数、今日活跃用户
  - 每张卡片含图标、数字、标题、同比/环比趋势
- 最近登录区（`grid-cols-1 md:grid-cols-2 gap-4`）：
  - 左侧：`Card` + `Table`（最近 10 条登录记录：用户名、时间、IP、状态）
  - 右侧：`Card` + 快捷操作按钮组（新增用户/新增角色/分配权限）

---

#### 页面 3：用户管理 `/users`

**布局结构**：主内容区，顶部工具栏 + 下方数据表格

**组件构成**：
- `PageHeader`：标题「用户管理」+ 右侧 `Button`「新增用户」
- 工具栏行（`flex flex-col md:flex-row gap-4`）：
  - `Input[search]`：按用户名/邮箱搜索
  - `Select`：按状态筛选（全部/启用/禁用）
  - `Select`：按角色筛选
  - （P1）批量操作按钮组：启用/禁用/删除
- `DataTable`（shadcn Table + 分页）：
  - 列：复选框、用户名、邮箱、角色（`Badge` 标签组）、状态（`Badge`：启用=绿/禁用=红）、创建时间、操作
  - 操作列：`DropdownMenu`（编辑/分配角色/重置密码/启用-禁用/删除）
  - 底部：`Pagination`（每页条数选择 + 页码导航）
- 弹窗（`Dialog`）：
  - 新增/编辑用户 Dialog：用户名、邮箱、密码（新增时必填/编辑时选填）、昵称、角色多选
  - 分配角色 Dialog：用户名只读 + `Checkbox` 组或 `MultiSelect` 角色列表
  - 删除确认 Dialog：`AlertDialog` 二次确认

---

#### 页面 4：角色管理 `/roles`

**布局结构**：同用户管理（工具栏 + 表格 + 弹窗）

**组件构成**：
- `PageHeader`：标题「角色管理」+ `Button`「新增角色」
- 工具栏：搜索框 + 角色状态筛选
- `DataTable`：
  - 列：角色名、描述、权限数量（`Badge`）、关联用户数（`Badge`）、创建时间、操作
  - 操作列：`DropdownMenu`（编辑/分配权限/查看用户/删除）
- 弹窗：
  - 新增/编辑角色 Dialog：角色名、描述、权限分配区
  - 权限分配 Dialog：左侧权限树（按模块分组的 `Tree` 或 `Checkbox` 组），右侧已选权限摘要
  - 删除确认：`AlertDialog`，如有关联用户需额外警告

---

#### 页面 5：权限管理 `/permissions`

**布局结构**：按模块分组的卡片/折叠面板布局

**组件构成**：
- `PageHeader`：标题「权限管理」+ `Button`「新增权限」
- 工具栏：搜索框 + 模块筛选 `Select`
- 权限列表区（按模块分组）：
  - 每个模块一个 `Card` 或 `Collapsible`：
    - 头部：模块名 + 权限数 `Badge`
    - 内容：`Table` 或 `Badge` 网格展示该模块下所有权限
    - 列：权限名称、权限标识（`code`，如 `user:read`）、描述、操作（编辑/删除）
- 弹窗：
  - 新增/编辑权限 Dialog：权限名称、权限标识（code）、所属模块（`Select`）、描述

---

#### 页面 6：个人中心 `/profile`（P1）

**布局结构**：左右分栏（左：个人信息表单，右：修改密码表单）

**组件构成**：
- 左侧 `Card`「个人信息」：
  - `Avatar`（头像，P2 可上传）
  - `Form`：用户名（只读）、昵称、邮箱、角色（只读 `Badge` 组）、创建时间（只读）
  - `Button`：保存修改
- 右侧 `Card`「修改密码」：
  - `Form`：旧密码、新密码、确认新密码
  - 密码强度指示器（`Progress` 或彩色 `Badge`）
  - `Button`：确认修改

---

#### 全局布局框架

**布局结构**：经典管理后台布局

```
┌─────────────────────────────────────────────┐
│  顶部栏（Logo + 面包屑 + 用户菜单 + 主题切换）     │
├──────────┬──────────────────────────────────┤
│          │                                  │
│  侧边栏   │       主内容区（路由出口）          │
│  导航菜单  │       含 PageHeader + 页面内容     │
│          │                                  │
│  - 仪表盘  │                                  │
│  - 用户    │                                  │
│  - 角色    │                                  │
│  - 权限    │                                  │
│  - 日志    │                                  │
│  - 个人中心 │                                  │
│          │                                  │
└──────────┴──────────────────────────────────┘
```

**组件构成**：
- `Sidebar`（shadcn）：导航菜单，含图标 + 文字；当前路由高亮；移动端收起为 `Sheet`（抽屉）
- `Header`：面包屑（`Breadcrumb`）+ 右侧用户下拉菜单（`DropdownMenu`：个人中心/退出登录）+ 主题切换 `Button`
- `Main`：`Outlet`（路由出口），页面切换加 `Fade` 过渡动画
- 响应式断点：`md`（768px）以下侧边栏转为抽屉模式

---

### 3.3 待确认问题

| # | 问题 | 影响范围 | 建议默认值 |
|---|------|----------|------------|
| Q1 | 注册功能是否对外开放？还是仅管理员可创建用户？ | 认证模块、登录页 UI | 建议：仅管理员创建用户，注册入口不对公网开放（更安全） |
| Q2 | 角色继承（父子角色）是否需要实现？如需要，继承层级深度是否限制？ | 角色管理、权限计算逻辑 | 建议：MVP 不实现继承，权限扁平分配；如有需求作为 P1 |
| Q3 | 权限粒度是否需要到「字段级」？（如：某角色只能查看用户邮箱但不能修改） | 权限模型设计、数据序列化 | 建议：MVP 控制到操作级（CRUD），字段级为 P2 |
| Q4 | 是否需要多租户支持？（同一系统内多个组织/公司数据隔离） | 数据模型、所有查询逻辑 | 建议：不需要多租户，单租户系统 |
| Q5 | JWT 的存储位置（localStorage vs httpOnly cookie）？影响 XSS 防护策略 | 前端 Token 管理、安全策略 | 建议：access_token 存内存（zustand/state），refresh_token 存 httpOnly cookie |
| Q6 | 数据库连接池配置参数？预计并发量？ | 后端配置、性能 | 已定：每进程默认 pool_size=5, max_overflow=5；按数据库总连接预算和实例数共同调整 |
| Q7 | 是否需要邮件验证（注册后发验证邮件）？需要 SMTP 配置 | 认证流程、基础设施 | 建议：MVP 不做邮件验证，P2 增强 |
| Q8 | 前端部署方式？静态文件托管 / Nginx 反代 / 嵌入后端？ | 部署架构、CI/CD | 建议：独立部署，Nginx 托管前端 + 反代后端 API |
| Q9 | 操作日志的存储策略？直接写数据库 / 异步队列 / 文件？ | 审计模块性能 | 建议：直接写数据库（MVP），量大后可改异步 |
| Q10 | 是否需要实时通知（如用户被分配新角色后推送）？ | 前端 WebSocket、后端推送 | 建议：不需要实时推送，用户下次登录时生效 |

---

## 4. 附录

### 4.1 术语表

| 术语 | 说明 |
|------|------|
| RBAC | Role-Based Access Control，基于角色的访问控制 |
| JWT | JSON Web Token；access token 自包含，但会结合服务端会话族和 token version 实现即时撤销 |
| Argon2id | 新密码使用的内存困难型密码哈希算法；旧 bcrypt 数据登录后渐进迁移 |
| Access Token | 访问令牌，短期有效（≤30min） |
| Refresh Token | 一次性刷新令牌，服务端只保存摘要；有效期内的已消费 token 重放会撤销整个会话族 |
| 软删除 | 数据不物理删除，标记 `is_deleted=True`，可恢复 |

### 4.2 数据模型概览

```
User（用户）
├── id, username, email, hashed_password, nickname
├── is_active, is_deleted, created_at, updated_at
└── M:N → Role

Role（角色）
├── id, name, description
├── is_deleted, created_at, updated_at
└── M:N → Permission

Permission（权限）
├── id, name, code（如 user:read）, module, description
├── is_deleted, created_at, updated_at
└── M:N ← Role

UserRole（用户-角色关联）
└── user_id, role_id, created_at

RolePermission（角色-权限关联）
└── role_id, permission_id, created_at

AuditLog（审计日志，P1）
└── id, user_id, action, target, detail, ip, created_at
    （仅追加表：运行时角色只有 SELECT/INSERT，保留策略由 DBA 按分区管理）

RefreshSessionFamily（refresh 会话族 — 撤销真源）
├── id, user_id, token_version, expires_at
└── revoked_at, revoked_reason, created_at, last_used_at

RefreshSession（refresh token 轮换历史）
├── id, user_id, jti, family_id, token_hash（HMAC 摘要，不存原文）
└── token_version, expires_at, revoked_at, revoked_reason, replaced_by_jti
```

> `User.token_version` 与会话族共同实现即时撤销：改密、停用、删除用户都会递增版本并撤销全部会话族，使已签发的 access token 立即失效。

### 4.3 API 端点规划

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | `/api/v1/auth/register` | 公开 | 用户注册 |
| POST | `/api/v1/auth/login` | 公开 | 用户登录 |
| POST | `/api/v1/auth/refresh` | refresh_token | 刷新 token |
| POST | `/api/v1/auth/logout` | 已认证 | 退出登录 |
| GET | `/api/v1/users` | `user:read` | 用户列表（分页/搜索/筛选） |
| POST | `/api/v1/users` | `user:create` | 新增用户 |
| GET | `/api/v1/users/{id}` | `user:read` | 用户详情 |
| PUT | `/api/v1/users/{id}` | `user:update` | 更新用户 |
| DELETE | `/api/v1/users/{id}` | `user:delete` | 删除用户（软删除） |
| PUT | `/api/v1/users/{id}/roles` | `user:assign` | 分配用户角色 |
| GET | `/api/v1/roles` | `role:read` | 角色列表 |
| POST | `/api/v1/roles` | `role:create` | 新增角色 |
| PUT | `/api/v1/roles/{id}` | `role:update` | 更新角色 |
| DELETE | `/api/v1/roles/{id}` | `role:delete` | 删除角色 |
| PUT | `/api/v1/roles/{id}/permissions` | `role:assign` | 分配角色权限 |
| GET | `/api/v1/permissions` | `permission:read` | 权限列表 |
| POST | `/api/v1/permissions` | `permission:create` | 新增权限 |
| PUT | `/api/v1/permissions/{id}` | `permission:update` | 更新权限 |
| DELETE | `/api/v1/permissions/{id}` | `permission:delete` | 删除权限 |
| GET | `/api/v1/me` | 已认证 | 个人信息（含 `permissions`：经启用角色授予的权限码集合，前端据此做界面级权限控制） |
| PUT | `/api/v1/me` | 已认证 | 修改个人信息 |
| PUT | `/api/v1/me/password` | 已认证 | 修改密码 |
| GET | `/api/v1/dashboard` | 已认证 | 仪表盘统计 |
| GET | `/api/v1/audit-logs` | `audit:read` | 审计日志（P1） |

---

> **文档结束**  
> 如有疑问或需修改，请联系产品经理 李剑桥。
