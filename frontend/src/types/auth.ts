/** 认证相关类型 */

/** 登录请求 */
export interface LoginRequest {
  username: string
  password: string
}

/** Token 响应 */
export interface TokenResponse {
  access_token: string
  token_type: string
}

/** 注册请求 */
export interface RegisterRequest {
  username: string
  email: string
  password: string
}

/** 当前用户信息 */
export interface UserInfo {
  id: number
  username: string
  email: string
  nickname: string
  is_active: boolean
  is_superuser: boolean
  created_at: string
  updated_at: string
  roles?: import("./role").Role[]
  permissions?: string[]
}
