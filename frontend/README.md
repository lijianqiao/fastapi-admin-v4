# Frontend — fastapi-admin

[中文文档](./README_zh.md) · [Root README](../README.md)

React SPA for the RBAC admin console: login, dashboard, users/roles/permissions, audit logs, and profile.

![Dashboard](../docs/images/dashboard.png)

## Stack

- React **19** + TypeScript + Vite **8**
- Tailwind CSS **4** + shadcn/ui (**Base UI** / `@base-ui/react`)
- Hugeicons, TanStack Table, React Hook Form + Zod
- Zustand auth store, React Router **7**, Axios
- Session restore via refresh cookie on app bootstrap

## Project layout

```text
frontend/
├── src/
│   ├── components/     # Layout, dialogs, ui primitives
│   ├── hooks/          # useAuth, usePermission, pagination helpers
│   ├── lib/            # API client, constants, icons
│   ├── pages/          # Route pages
│   ├── store/          # Zustand
│   └── types/
├── .env.example
└── package.json
```

## Setup

```bash
cd frontend
cp .env.example .env
pnpm install   # or: npm install
```

`.env`:

```ini
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

Ensure the backend is running and CORS includes `http://localhost:5173`.

## Scripts

```bash
pnpm run dev         # http://localhost:5173
pnpm run build       # tsc -b && vite build
pnpm run typecheck   # tsc -b --force
pnpm run lint
pnpm run preview
```

## Auth & permissions (UI)

- Access token is kept in memory; refresh token lives in an HttpOnly cookie
- On startup, `bootstrap()` refreshes once (single-flight) then loads `/me`
- Menu items and action buttons use `PERMISSIONS` from `src/lib/constants.ts`
- Superusers bypass permission checks in the UI; API still enforces rules server-side

## Screenshots

See the [root README](../README.md#screenshots) gallery (`docs/images/`).

## Notes

- Prefer Base UI patterns from the installed shadcn components (`render=` instead of Radix `asChild` where applicable)
- Forms should use the registry `field` components so validation messages surface correctly
