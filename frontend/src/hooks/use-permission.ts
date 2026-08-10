/** 权限校验 hook

 * 提供 hasPermission 函数检查当前用户是否拥有指定权限码。
 */

import { useCallback } from "react"

import { useAuthStore } from "@/store/auth"

export function usePermission() {
  const permissions = useAuthStore((state) => state.permissions)
  const isSuperuser = useAuthStore((state) => state.user?.is_superuser ?? false)

  /** 检查是否拥有指定权限 */
  const hasPermission = useCallback(
    (code: string): boolean => {
      // 超级管理员拥有所有权限
      if (isSuperuser) return true
      return permissions.includes(code)
    },
    [isSuperuser, permissions]
  )

  /** 检查是否拥有任意一个权限 */
  const hasAnyPermission = useCallback(
    (codes: string[]): boolean => {
      if (isSuperuser) return true
      return codes.some((code) => permissions.includes(code))
    },
    [isSuperuser, permissions]
  )

  /** 检查是否拥有全部权限 */
  const hasAllPermissions = useCallback(
    (codes: string[]): boolean => {
      if (isSuperuser) return true
      return codes.every((code) => permissions.includes(code))
    },
    [isSuperuser, permissions]
  )

  return {
    permissions,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
  }
}
