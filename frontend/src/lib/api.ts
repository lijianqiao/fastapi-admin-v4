/** Axios HTTP 客户端实例 + 拦截器

 * - 请求拦截器：自动携带 access_token
 * - 响应拦截器：401 自动刷新 token，失败跳转登录
 */

import axios, {
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from "axios"

import { ROUTES } from "@/lib/constants"
import { useAuthStore } from "@/store/auth"

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1"

/** Axios 实例 */
const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  withCredentials: true,
})

// ===== Token 管理（内存，不持久化） =====
let accessToken: string | null = null

/** 设置 access_token，同时同步到 zustand store，避免两处状态不一致 */
export function setAccessToken(token: string | null): void {
  accessToken = token
  useAuthStore.getState().setToken(token)
}

/** 获取 access_token */
export function getAccessToken(): string | null {
  return accessToken
}

const REFRESH_LOCK_NAME = "fastapi-admin:auth-refresh"

/** 用 refresh_token cookie 换取新的 access_token（不做跨标签页协调） */
async function requestNewAccessToken(): Promise<string> {
  const response = await axios.post(
    `${BASE_URL}/auth/refresh`,
    {},
    { withCredentials: true }
  )
  const newToken = response.data?.data?.access_token
  if (!newToken) {
    throw new Error("No access_token in refresh response")
  }
  setAccessToken(newToken)
  return newToken
}

/** 刷新 access_token
 *
 * refresh_token 是一次性的：两个标签页带着同一个 Cookie 并发刷新时，后到者会被服务端
 * 判定为重放，并撤销整个会话族，所有标签页都会被登出。这里用 Web Locks 让所有标签页
 * 的刷新串行执行：后拿到锁的标签页发请求时，浏览器已经存下前一个标签页轮换出的新 Cookie。
 * 不支持 Web Locks 的环境（非安全上下文等）退化为直接请求。
 */
export function refreshAccessToken(): Promise<string> {
  if ("locks" in navigator) {
    return navigator.locks.request(REFRESH_LOCK_NAME, requestNewAccessToken)
  }
  return requestNewAccessToken()
}

/** 从 axios 错误中取出后端统一错误信封的 message，取不到时返回 fallback */
export function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { message?: unknown } | undefined
    if (typeof data?.message === "string" && data.message) {
      return data.message
    }
  }
  return fallback
}

// ===== 请求拦截器：自动携带 access_token =====
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// ===== 响应拦截器：401 自动刷新 token =====
let isRefreshing = false
let failedQueue: Array<{
  resolve: (value?: unknown) => void
  reject: (error: unknown) => void
}> = []

function processQueue(error: unknown): void {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve()
    }
  })
  failedQueue = []
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // 非 401 错误或已重试过，直接拒绝
    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error)
    }

    // 登录接口本身返回 401（账号或密码错误）不触发刷新，交给调用方处理
    if (originalRequest.url?.includes("/auth/login")) {
      return Promise.reject(error)
    }

    // 如果是刷新 token 的请求失败，直接跳转登录
    if (originalRequest.url?.includes("/auth/refresh")) {
      setAccessToken(null)
      window.location.href = ROUTES.LOGIN
      return Promise.reject(error)
    }

    // 如果正在刷新，将请求加入队列等待
    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject })
      }).then(() => {
        originalRequest.headers.Authorization = `Bearer ${accessToken}`
        return api(originalRequest)
      })
    }

    // 开始刷新 token
    originalRequest._retry = true
    isRefreshing = true

    try {
      const newToken = await refreshAccessToken()
      processQueue(null)
      originalRequest.headers.Authorization = `Bearer ${newToken}`
      return api(originalRequest)
    } catch (refreshError) {
      setAccessToken(null)
      processQueue(refreshError)
      window.location.href = ROUTES.LOGIN
      return Promise.reject(refreshError)
    } finally {
      isRefreshing = false
    }
  }
)

export default api
