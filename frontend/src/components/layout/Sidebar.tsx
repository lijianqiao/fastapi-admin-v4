/** 侧边导航栏

 * 桌面端支持展开/收缩；用户菜单固定在侧栏底部。
 * 移动端通过 Sheet 抽屉显示完整导航。
 */

import { NavLink, useNavigate } from "react-router"

import {
  Dashboard02Icon,
  UserMultipleIcon,
  Shield02Icon,
  Key02Icon,
  FileEditIcon,
  UserCircleIcon,
  Logout02Icon,
} from "@/lib/icons"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { useAuth } from "@/hooks/use-auth"
import { usePermission } from "@/hooks/use-permission"
import { ROUTES, PERMISSIONS } from "@/lib/constants"
import { cn } from "@/lib/utils"

interface SidebarProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  collapsed: boolean
}

interface NavItem {
  label: string
  path: string
  icon: typeof Dashboard02Icon
  permission?: string
}

const NAV_ITEMS: NavItem[] = [
  { label: "仪表盘", path: ROUTES.DASHBOARD, icon: Dashboard02Icon },
  {
    label: "用户管理",
    path: ROUTES.USERS,
    icon: UserMultipleIcon,
    permission: PERMISSIONS.USER_READ,
  },
  {
    label: "角色管理",
    path: ROUTES.ROLES,
    icon: Shield02Icon,
    permission: PERMISSIONS.ROLE_READ,
  },
  {
    label: "权限管理",
    path: ROUTES.PERMISSIONS,
    icon: Key02Icon,
    permission: PERMISSIONS.PERMISSION_READ,
  },
  {
    label: "操作日志",
    path: ROUTES.AUDIT,
    icon: FileEditIcon,
    permission: PERMISSIONS.AUDIT_READ,
  },
  { label: "个人中心", path: ROUTES.PROFILE, icon: UserCircleIcon },
]

function navLinkClassName(isActive: boolean, collapsed: boolean) {
  return cn(
    "flex items-center rounded-lg py-2 text-sm font-medium transition-colors",
    collapsed ? "justify-center px-2" : "gap-3 px-3",
    isActive
      ? "bg-primary text-primary-foreground"
      : "text-muted-foreground hover:bg-muted hover:text-foreground"
  )
}

function NavList({
  collapsed,
  onNavigate,
}: {
  collapsed: boolean
  onNavigate?: () => void
}) {
  const { hasPermission } = usePermission()
  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.permission || hasPermission(item.permission)
  )

  return (
    <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-3">
      {visibleItems.map((item) => {
        const Icon = item.icon
        const link = (
          <NavLink
            key={item.path}
            to={item.path}
            onClick={onNavigate}
            className={({ isActive }) => navLinkClassName(isActive, collapsed)}
            title={collapsed ? item.label : undefined}
          >
            <Icon className="size-4 shrink-0" />
            <span className={cn(collapsed && "sr-only")}>{item.label}</span>
          </NavLink>
        )

        if (!collapsed) {
          return link
        }

        return (
          <Tooltip key={item.path}>
            <TooltipTrigger
              render={
                <NavLink
                  to={item.path}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    navLinkClassName(isActive, collapsed)
                  }
                />
              }
            >
              <Icon className="size-4 shrink-0" />
              <span className="sr-only">{item.label}</span>
            </TooltipTrigger>
            <TooltipContent side="right" sideOffset={8}>
              {item.label}
            </TooltipContent>
          </Tooltip>
        )
      })}
    </nav>
  )
}

function UserMenu({ collapsed }: { collapsed: boolean }) {
  const navigate = useNavigate()
  const { user, logout } = useAuth()

  const initials =
    user?.nickname?.charAt(0)?.toUpperCase() ||
    user?.username?.charAt(0)?.toUpperCase() ||
    "U"
  const displayName = user?.nickname || user?.username || "用户"

  return (
    <div className="border-t p-3">
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="ghost"
              className={cn(
                "h-auto w-full px-2 py-2",
                collapsed ? "justify-center" : "justify-start gap-2"
              )}
              aria-label={collapsed ? displayName : undefined}
            />
          }
        >
          <Avatar className="size-8">
            <AvatarFallback className="text-xs">{initials}</AvatarFallback>
          </Avatar>
          {!collapsed && (
            <span className="truncate text-sm font-medium">{displayName}</span>
          )}
        </DropdownMenuTrigger>
        <DropdownMenuContent
          side={collapsed ? "right" : "top"}
          align={collapsed ? "end" : "start"}
          sideOffset={8}
          className="w-48"
        >
          <DropdownMenuGroup>
            <DropdownMenuItem onClick={() => navigate(ROUTES.PROFILE)}>
              <UserCircleIcon />
              <span>个人中心</span>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={logout} variant="destructive">
              <Logout02Icon />
              <span>退出登录</span>
            </DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}

function SidebarBrand({ collapsed }: { collapsed: boolean }) {
  return (
    <div
      className={cn(
        "flex h-16 shrink-0 items-center border-b",
        collapsed ? "justify-center px-2" : "gap-2 px-4"
      )}
    >
      <Shield02Icon className="size-6 shrink-0 text-primary" />
      {!collapsed && (
        <span className="truncate text-lg font-semibold">权限管理系统</span>
      )}
    </div>
  )
}

export function Sidebar({ open, onOpenChange, collapsed }: SidebarProps) {
  return (
    <>
      <aside
        className={cn(
          "hidden shrink-0 border-r bg-sidebar transition-[width] duration-200 md:flex md:flex-col",
          collapsed ? "w-16" : "w-60"
        )}
      >
        <SidebarBrand collapsed={collapsed} />
        <NavList collapsed={collapsed} />
        <UserMenu collapsed={collapsed} />
      </aside>

      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="left" className="flex w-64 flex-col p-0">
          <SheetHeader className="border-b">
            <SheetTitle className="flex items-center gap-2">
              <Shield02Icon className="size-5 text-primary" />
              权限管理系统
            </SheetTitle>
          </SheetHeader>
          <NavList
            collapsed={false}
            onNavigate={() => onOpenChange(false)}
          />
          <UserMenu collapsed={false} />
        </SheetContent>
      </Sheet>
    </>
  )
}
