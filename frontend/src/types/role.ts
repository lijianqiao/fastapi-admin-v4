/** 角色相关类型 */

import type { Permission } from "./permission"

/** 角色基础信息 */
export interface Role {
  id: number
  name: string
  description: string
  is_active: boolean
  created_at: string
  updated_at: string
}

/** 角色信息（含权限） */
export interface RoleWithPermissions extends Role {
  permissions: Permission[]
  user_count?: number
}

/** 创建角色请求 */
export interface RoleCreate {
  name: string
  description?: string
  permission_ids?: number[]
}

/** 更新角色请求 */
export interface RoleUpdate {
  name?: string
  description?: string
  is_active?: boolean
}

/** 分配权限请求 */
export interface AssignPermissionsRequest {
  permission_ids: number[]
}

/** 角色查询参数 */
export interface RoleQueryParams {
  page?: number
  page_size?: number
  search?: string
}
