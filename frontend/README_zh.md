# 前端 — fastapi-admin

[English](./README.md) · [根目录说明](../README_zh.md)

RBAC 管理后台的 React SPA：登录、仪表盘、用户/角色/权限、操作日志与个人中心。

![仪表盘](../docs/images/dashboard.png)

## 技术栈

- React **19** + TypeScript + Vite **8**
- Tailwind CSS **4** + shadcn/ui（**Base UI** / `@base-ui/react`）
- Hugeicons、TanStack Table、React Hook Form + Zod
- Zustand 认证状态、React Router **7**、Axios
- 启动时通过 refresh Cookie 恢复会话

## 目录结构

```text
frontend/
├── src/
│   ├── components/     # 布局、对话框、UI 组件
│   ├── hooks/          # useAuth、usePermission、分页等
│   ├── lib/            # API 客户端、常量、图标
│   ├── pages/          # 页面
│   ├── store/          # Zustand
│   └── types/
├── .env.example
└── package.json
```

## 环境准备

```bash
cd frontend
cp .env.example .env
pnpm install   # 或 npm install
```

`.env`：

```ini
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

请确保后端已启动，且 CORS 包含 `http://localhost:5173`。

## 常用脚本

```bash
pnpm run dev         # http://localhost:5173
pnpm run build       # tsc -b && vite build
pnpm run typecheck   # tsc -b --force
pnpm run lint
pnpm run preview
```

## 认证与权限（前端）

- access token 存放于内存；refresh token 使用 HttpOnly Cookie
- 启动时 `bootstrap()` 单飞刷新一次会话，再请求 `/me`
- 菜单与操作按钮使用 `src/lib/constants.ts` 中的 `PERMISSIONS`
- 超管在前端绕过权限展示限制；真正鉴权仍在后端接口完成

## 截图

完整界面预览见 [根目录 README](../README_zh.md#界面预览)（`docs/images/`）。

## 说明

- 组件遵循已安装的 shadcn Base UI 用法（按需使用 `render=`，而非 Radix 的 `asChild`）
- 表单建议使用 registry 的 `field` 组件，以便正确展示校验错误
