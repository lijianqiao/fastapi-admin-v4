/** API 统一响应类型 */

/** 统一响应信封 */
export interface ApiResponse<T = unknown> {
  code: number
  data: T
  message: string
}

/** 分页数据结构 */
export interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

/** 分页响应 */
export type PaginatedResponse<T> = ApiResponse<PaginatedData<T>>

/** API 错误 */
export interface ApiError {
  code: number
  message: string
  data: null
}

/** 分页查询参数 */
export interface PaginationParams {
  page?: number
  page_size?: number
  search?: string
}
