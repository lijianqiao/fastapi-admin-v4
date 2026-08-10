/** Zustand auth store

 * 管理 access_token、当前用户信息和权限码列表。
 * token 仅存储在内存中，不持久化到 localStorage。
 */

import { create } from "zustand"

import type { CurrentUser } from "@/types/user"

interface AuthState {
  /** access_token（仅内存） */
  token: string | null
  /** 当前用户信息 */
  user: CurrentUser | null
  /** 权限码列表 */
  permissions: string[]
  /** 是否已认证 */
  isAuthenticated: boolean
  /** 是否正在加载 */
  isLoading: boolean
  /** 应用启动时的会话恢复检查是否已完成 */
  isInitialized: boolean

  /** 设置 token */
  setToken: (token: string | null) => void
  /** 设置当前用户 */
  setUser: (user: CurrentUser | null) => void
  /** 设置权限码列表 */
  setPermissions: (permissions: string[]) => void
  /** 设置加载状态 */
  setLoading: (loading: boolean) => void
  /** 标记会话恢复检查已完成 */
  setInitialized: (initialized: boolean) => void
  /** 登出：清除所有状态 */
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  permissions: [],
  isAuthenticated: false,
  isLoading: false,
  isInitialized: false,

  setToken: (token) => set({ token, isAuthenticated: token !== null }),

  setUser: (user) => set({ user }),

  setPermissions: (permissions) => set({ permissions }),

  setLoading: (isLoading) => set({ isLoading }),

  setInitialized: (isInitialized) => set({ isInitialized }),

  logout: () =>
    set({
      token: null,
      user: null,
      permissions: [],
      isAuthenticated: false,
      isLoading: false,
    }),
}))
