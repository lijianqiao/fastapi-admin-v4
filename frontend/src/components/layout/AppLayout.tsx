/** 主布局组件

 * 包含侧边栏 + 顶部栏 + 主内容区（路由出口）。
 * 响应式：移动端侧边栏转为 Sheet 抽屉；桌面端支持展开/收缩。
 */

import { useEffect, useState } from "react"
import { Outlet } from "react-router"

import { Header } from "@/components/layout/Header"
import { Sidebar } from "@/components/layout/Sidebar"
import { STORAGE_KEYS } from "@/lib/constants"

function readCollapsedPreference(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEYS.SIDEBAR_COLLAPSED) === "true"
  } catch {
    return false
  }
}

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(readCollapsedPreference)

  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEYS.SIDEBAR_COLLAPSED,
        collapsed ? "true" : "false"
      )
    } catch {
      // 忽略隐私模式下的写入失败
    }
  }, [collapsed])

  return (
    <div className="flex h-svh overflow-hidden bg-background">
      <Sidebar
        open={sidebarOpen}
        onOpenChange={setSidebarOpen}
        collapsed={collapsed}
      />

      <div className="flex flex-1 flex-col overflow-hidden">
        <Header
          onMenuClick={() => setSidebarOpen(true)}
          collapsed={collapsed}
          onCollapsedChange={setCollapsed}
        />
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
