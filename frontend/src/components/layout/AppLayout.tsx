/** 主布局组件

 * 包含侧边栏 + 顶部栏 + 主内容区（路由出口）。
 * 响应式：移动端侧边栏转为 Sheet 抽屉。
 */

import { useState } from "react"
import { Outlet } from "react-router"

import { Header } from "@/components/layout/Header"
import { Sidebar } from "@/components/layout/Sidebar"

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex h-svh overflow-hidden bg-background">
      {/* 桌面端侧边栏 */}
      <Sidebar open={sidebarOpen} onOpenChange={setSidebarOpen} />

      {/* 主内容区 */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
