/** 路由路径常量 */
export const ROUTES = {
  LOGIN: "/login",
  DASHBOARD: "/",
  USERS: "/users",
  USERS_TRASH: "/users/trash",
  ROLES: "/roles",
  ROLES_TRASH: "/roles/trash",
  PERMISSIONS: "/permissions",
  PERMISSIONS_TRASH: "/permissions/trash",
  PROFILE: "/profile",
  AUDIT: "/audit",
  FORBIDDEN: "/403",
  NOT_FOUND: "*",
} as const

/** 权限码常量 — 与后端权限定义保持一致 */
export const PERMISSIONS = {
  // 用户模块
  USER_READ: "user:read",
  USER_CREATE: "user:create",
  USER_UPDATE: "user:update",
  USER_DELETE: "user:delete",
  USER_ASSIGN: "user:assign",
  USER_RESET_PASSWORD: "user:reset_password",
  // 角色模块
  ROLE_READ: "role:read",
  ROLE_CREATE: "role:create",
  ROLE_UPDATE: "role:update",
  ROLE_DELETE: "role:delete",
  ROLE_ASSIGN: "role:assign",
  // 权限模块
  PERMISSION_READ: "permission:read",
  PERMISSION_CREATE: "permission:create",
  PERMISSION_UPDATE: "permission:update",
  PERMISSION_DELETE: "permission:delete",
  // 审计模块
  AUDIT_READ: "audit:read",
} as const

/** localStorage 存储键 */
export const STORAGE_KEYS = {
  THEME: "theme",
  SIDEBAR_COLLAPSED: "sidebar-collapsed",
} as const

/** 默认分页配置 */
export const DEFAULT_PAGE_SIZE = 10
export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100]

/** API 基础路径 */
export const API_BASE_URL = "/api/v1"
