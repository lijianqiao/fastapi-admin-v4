/** 权限校验 hook

 * 提供 hasPermission 函数检查当前用户是否拥有指定权限码。
 */

import { useAuthStore } from "@/store/auth"

export function usePermission() {
  const permissions = useAuthStore((state) => state.permissions)
  const user = useAuthStore((state) => state.user)

  /** 检查是否拥有指定权限 */
  const hasPermission = (code: string): boolean => {
    // 超级管理员拥有所有权限
    if (user?.is_superuser) return true
    return permissions.includes(code)
  }

  /** 检查是否拥有任意一个权限 */
  const hasAnyPermission = (codes: string[]): boolean => {
    if (user?.is_superuser) return true
    return codes.some((code) => permissions.includes(code))
  }

  /** 检查是否拥有全部权限 */
  const hasAllPermissions = (codes: string[]): boolean => {
    if (user?.is_superuser) return true
    return codes.every((code) => permissions.includes(code))
  }

  return {
    permissions,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
  }
}
