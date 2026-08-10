/** 类型统一导出 */

export type {
  ApiResponse,
  PaginatedData,
  PaginatedResponse,
  ApiError,
  PaginationParams,
} from "./api"
export type { LoginRequest, TokenResponse, RegisterRequest } from "./auth"
export type {
  User,
  UserWithRoles,
  CurrentUser,
  UserCreate,
  UserUpdate,
  AssignRolesRequest,
  ChangePasswordRequest,
  UpdateProfileRequest,
  UserQueryParams,
} from "./user"
export type {
  Role,
  RoleWithPermissions,
  RoleCreate,
  RoleUpdate,
  AssignPermissionsRequest,
  RoleQueryParams,
} from "./role"
export type {
  Permission,
  PermissionCreate,
  PermissionUpdate,
  PermissionQueryParams,
  GroupedPermissions,
} from "./permission"
export type {
  AuditLog,
  AuditLogQueryParams,
  DashboardStats,
  RecentLoginItem,
  DashboardData,
} from "./audit"
