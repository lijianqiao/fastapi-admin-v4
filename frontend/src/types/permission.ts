/** 权限相关类型 */

/** 权限信息 */
export interface Permission {
  id: number
  name: string
  code: string
  module: string
  description: string
  is_active: boolean
  created_at: string
  updated_at: string
}

/** 创建权限请求 */
export interface PermissionCreate {
  name: string
  code: string
  module?: string
  description?: string
}

/** 更新权限请求 */
export interface PermissionUpdate {
  name?: string
  code?: string
  module?: string
  description?: string
  is_active?: boolean
}

/** 权限查询参数 */
export interface PermissionQueryParams {
  page?: number
  page_size?: number
  search?: string
  module?: string
  grouped?: boolean
}

/** 按模块分组的权限 */
export type GroupedPermissions = Record<string, Permission[]>
