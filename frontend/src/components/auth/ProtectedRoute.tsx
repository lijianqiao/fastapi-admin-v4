/** 路由守卫组件

 * 未登录跳转登录页，无权限显示 403 提示。
 */

import type { ReactNode } from "react"
import { Navigate, useLocation } from "react-router"

import { useAuthStore } from "@/store/auth"
import { ROUTES } from "@/lib/constants"

interface ProtectedRouteProps {
  children: ReactNode
  /** 需要的权限码，不传则只检查登录状态 */
  permission?: string
}

export function ProtectedRoute({ children, permission }: ProtectedRouteProps) {
  const location = useLocation()
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const permissions = useAuthStore((state) => state.permissions)
  const user = useAuthStore((state) => state.user)

  // 未认证跳转登录
  if (!isAuthenticated) {
    return <Navigate to={ROUTES.LOGIN} state={{ from: location }} replace />
  }

  // 检查权限（超级管理员跳过权限检查）
  if (permission && !user?.is_superuser && !permissions.includes(permission)) {
    return <Navigate to={ROUTES.FORBIDDEN} replace />
  }

  return <>{children}</>
}
