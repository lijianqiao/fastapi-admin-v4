/** 认证 hook

 * 封装 auth store + API 调用，提供 login, logout, fetchProfile 等。
 */

import { useCallback } from "react"

import api, { setAccessToken } from "@/lib/api"
import { ROUTES } from "@/lib/constants"
import { useAuthStore } from "@/store/auth"
import type { LoginRequest } from "@/types/auth"
import type { UserInfo, UserWithRoles } from "@/types/user"

export function useAuth() {
  const { token, user, permissions, isAuthenticated, isLoading, setToken, setUser, setPermissions, setLoading, logout } =
    useAuthStore()

  /** 登录 */
  const login = useCallback(
    async (credentials: LoginRequest): Promise<void> => {
      setLoading(true)
      try {
        const formData = new URLSearchParams()
        formData.append("username", credentials.username)
        formData.append("password", credentials.password)

        const response = await api.post("/auth/login", formData, {
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
        })

        const accessToken = response.data?.data?.access_token
        if (!accessToken) {
          throw new Error("登录失败：未获取到 access_token")
        }

        setAccessToken(accessToken)
        setToken(accessToken)

        // 获取用户信息
        const profileResponse = await api.get("/me")
        const userInfo: UserWithRoles = profileResponse.data?.data
        if (userInfo) {
          setUser(userInfo)
          // 从角色中提取权限码
          const permCodes = userInfo.roles?.flatMap((role) =>
            role.permissions?.map((p) => p.code) ?? [],
          ) ?? []
          setPermissions(permCodes)
        }
      } finally {
        setLoading(false)
      }
    },
    [setToken, setUser, setPermissions, setLoading],
  )

  /** 退出登录 */
  const logoutAction = useCallback(async (): Promise<void> => {
    try {
      await api.post("/auth/logout")
    } catch {
      // 忽略退出登录的 API 错误
    } finally {
      setAccessToken(null)
      logout()
      window.location.href = ROUTES.LOGIN
    }
  }, [logout])

  /** 获取个人信息 */
  const fetchProfile = useCallback(async (): Promise<UserInfo | null> => {
    try {
      const response = await api.get("/me")
      const userInfo: UserWithRoles = response.data?.data
      if (userInfo) {
        setUser(userInfo)
        const permCodes = userInfo.roles?.flatMap((role) =>
          role.permissions?.map((p) => p.code) ?? [],
        ) ?? []
        setPermissions(permCodes)
        return userInfo
      }
    } catch {
      // token 可能已过期
    }
    return null
  }, [setUser, setPermissions])

  return {
    token,
    user,
    permissions,
    isAuthenticated,
    isLoading,
    login,
    logout: logoutAction,
    fetchProfile,
  }
}
