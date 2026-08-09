/** 用户相关类型 */

import type { Role } from "./role"

/** 用户基础信息 */
export interface User {
  id: number
  username: string
  email: string
  nickname: string
  is_active: boolean
  is_superuser: boolean
  created_at: string
  updated_at: string
}

/** 用户信息（含角色） */
export interface UserWithRoles extends User {
  roles: Role[]
}

/** 个人信息（GET/PATCH /me）：权限码由后端展开后下发，无法从 roles 推导 */
export interface CurrentUser extends UserWithRoles {
  permissions: string[]
}

/** 创建用户请求 */
export interface UserCreate {
  username: string
  email: string
  password: string
  nickname?: string
  role_ids?: number[]
}

/** 更新用户请求 */
export interface UserUpdate {
  email?: string
  nickname?: string
  is_active?: boolean
}

/** 分配角色请求 */
export interface AssignRolesRequest {
  role_ids: number[]
}

/** 修改密码请求 */
export interface ChangePasswordRequest {
  old_password: string
  new_password: string
}

/** 更新个人信息请求 */
export interface UpdateProfileRequest {
  nickname?: string
  email?: string
}

/** 用户查询参数 */
export interface UserQueryParams {
  page?: number
  page_size?: number
  search?: string
  is_active?: boolean | null
  role_id?: number | null
}
