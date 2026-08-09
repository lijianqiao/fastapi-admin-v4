/** Zustand auth store

 * 管理 access_token、当前用户信息和权限码列表。
 * token 仅存储在内存中，不持久化到 localStorage。
 */

import { create } from "zustand"

import type { UserInfo } from "@/types/auth"

interface AuthState {
  /** access_token（仅内存） */
  token: string | null
  /** 当前用户信息 */
  user: UserInfo | null
  /** 权限码列表 */
  permissions: string[]
  /** 是否已认证 */
  isAuthenticated: boolean
  /** 是否正在加载 */
  isLoading: boolean

  /** 设置 token */
  setToken: (token: string | null) => void
  /** 设置当前用户 */
  setUser: (user: UserInfo | null) => void
  /** 设置权限码列表 */
  setPermissions: (permissions: string[]) => void
  /** 设置加载状态 */
  setLoading: (loading: boolean) => void
  /** 登出：清除所有状态 */
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  permissions: [],
  isAuthenticated: false,
  isLoading: false,

  setToken: (token) =>
    set({ token, isAuthenticated: token !== null }),

  setUser: (user) => set({ user }),

  setPermissions: (permissions) => set({ permissions }),

  setLoading: (isLoading) => set({ isLoading }),

  logout: () =>
    set({
      token: null,
      user: null,
      permissions: [],
      isAuthenticated: false,
      isLoading: false,
    }),
}))
