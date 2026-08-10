/** 认证 hook

 * 封装 auth store + API 调用，提供 login, logout, fetchProfile, bootstrap 等。
 */

import { useCallback } from "react"

import api, { refreshAccessToken, setAccessToken } from "@/lib/api"
import { ROUTES } from "@/lib/constants"
import { useAuthStore } from "@/store/auth"
import type { LoginRequest } from "@/types/auth"
import type { CurrentUser } from "@/types/user"

// Module scope so it survives React StrictMode's double-invoked mount effect:
// refresh_token is single-use, so a second concurrent /auth/refresh call would
// replay the already-rotated cookie and trip the server's family revocation.
let bootstrapPromise: Promise<void> | null = null

export function useAuth() {
  const token = useAuthStore((state) => state.token)
  const user = useAuthStore((state) => state.user)
  const permissions = useAuthStore((state) => state.permissions)
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const isLoading = useAuthStore((state) => state.isLoading)
  const isInitialized = useAuthStore((state) => state.isInitialized)
  const setUser = useAuthStore((state) => state.setUser)
  const setPermissions = useAuthStore((state) => state.setPermissions)
  const setLoading = useAuthStore((state) => state.setLoading)
  const setInitialized = useAuthStore((state) => state.setInitialized)
  const logout = useAuthStore((state) => state.logout)

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

        // 获取用户信息
        const profileResponse = await api.get("/me")
        const userInfo: CurrentUser = profileResponse.data?.data
        if (userInfo) {
          setUser(userInfo)
          setPermissions(userInfo.permissions ?? [])
        }
      } finally {
        setLoading(false)
      }
    },
    [setUser, setPermissions, setLoading]
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
  const fetchProfile = useCallback(async (): Promise<CurrentUser | null> => {
    try {
      const response = await api.get("/me")
      const userInfo: CurrentUser = response.data?.data
      if (userInfo) {
        setUser(userInfo)
        setPermissions(userInfo.permissions ?? [])
        return userInfo
      }
    } catch {
      // token 可能已过期
    }
    return null
  }, [setUser, setPermissions])

  /** 应用启动时用 refresh_token cookie 尝试恢复会话，无论成败都会标记初始化完成

   * 同一次页面加载内只会真正执行一次（见 bootstrapPromise 的注释）。
   */
  const bootstrap = useCallback((): Promise<void> => {
    if (!bootstrapPromise) {
      bootstrapPromise = (async () => {
        try {
          await refreshAccessToken()
          await fetchProfile()
        } catch {
          // 没有有效的 refresh_token，保持未登录状态
        } finally {
          setInitialized(true)
        }
      })()
    }
    return bootstrapPromise
  }, [fetchProfile, setInitialized])

  return {
    token,
    user,
    permissions,
    isAuthenticated,
    isLoading,
    isInitialized,
    login,
    logout: logoutAction,
    fetchProfile,
    bootstrap,
  }
}
