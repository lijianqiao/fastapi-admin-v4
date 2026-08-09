/** 侧边导航栏

 * 桌面端固定侧边栏，移动端通过 Sheet 抽屉显示。
 */

import { NavLink } from "react-router"

import {
  Dashboard02Icon,
  UserMultipleIcon,
  Shield02Icon,
  Key02Icon,
  FileEditIcon,
  UserCircleIcon,
} from "@/lib/icons"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { cn } from "@/lib/utils"
import { ROUTES, PERMISSIONS } from "@/lib/constants"

interface SidebarProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

interface NavItem {
  label: string
  path: string
  icon: typeof Dashboard02Icon
  permission?: string
}

const NAV_ITEMS: NavItem[] = [
  { label: "仪表盘", path: ROUTES.DASHBOARD, icon: Dashboard02Icon },
  { label: "用户管理", path: ROUTES.USERS, icon: UserMultipleIcon, permission: PERMISSIONS.USER_READ },
  { label: "角色管理", path: ROUTES.ROLES, icon: Shield02Icon, permission: PERMISSIONS.ROLE_READ },
  { label: "权限管理", path: ROUTES.PERMISSIONS, icon: Key02Icon, permission: PERMISSIONS.PERMISSION_READ },
  { label: "操作日志", path: ROUTES.AUDIT, icon: FileEditIcon, permission: PERMISSIONS.AUDIT_READ },
  { label: "个人中心", path: ROUTES.PROFILE, icon: UserCircleIcon },
]

function NavList() {
  return (
    <nav className="flex flex-col gap-1 p-3">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon
        return (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )
            }
          >
            <Icon className="size-4" />
            <span>{item.label}</span>
          </NavLink>
        )
      })}
    </nav>
  )
}

export function Sidebar({ open, onOpenChange }: SidebarProps) {
  return (
    <>
      {/* 桌面端固定侧边栏 */}
      <aside className="hidden w-60 shrink-0 border-r bg-sidebar md:flex md:flex-col">
        <div className="flex h-16 items-center gap-2 border-b px-6">
          <Shield02Icon className="size-6 text-primary" />
          <span className="text-lg font-semibold">权限管理系统</span>
        </div>
        <NavList />
      </aside>

      {/* 移动端 Sheet 抽屉 */}
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="left" className="w-64 p-0">
          <SheetHeader className="border-b">
            <SheetTitle className="flex items-center gap-2">
              <Shield02Icon className="size-5 text-primary" />
              权限管理系统
            </SheetTitle>
          </SheetHeader>
          <NavList />
        </SheetContent>
      </Sheet>
    </>
  )
}
