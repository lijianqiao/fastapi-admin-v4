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
