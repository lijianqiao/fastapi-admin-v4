/** 审计日志相关类型 */

/** 审计日志 */
export interface AuditLog {
  id: number
  user_id: number | null
  username: string | null
  action: string
  target: string
  detail: string
  ip: string
  created_at: string
}

/** 审计日志查询参数 */
export interface AuditLogQueryParams {
  page?: number
  page_size?: number
  user_id?: number
  action?: string
}

/** 仪表盘统计 */
export interface DashboardStats {
  user_count: number
  role_count: number
  permission_count: number
  active_user_count: number
}

/** 最近登录记录 */
export interface RecentLoginItem {
  id: number
  user_id: number | null
  username: string | null
  action: string
  ip: string
  created_at: string
}

/** 仪表盘数据 */
export interface DashboardData {
  stats: DashboardStats
  recent_logs: RecentLoginItem[]
}
