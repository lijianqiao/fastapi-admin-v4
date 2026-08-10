/** 侧边导航栏

 * 桌面端支持展开/收缩与分组大菜单；用户菜单固定在侧栏底部。
 * 移动端通过 Sheet 抽屉显示完整导航。
 */

import { useEffect, useMemo, useState } from "react"
import { NavLink, useLocation, useNavigate } from "react-router"

import {
  Dashboard02Icon,
  UserMultipleIcon,
  Shield02Icon,
  Key02Icon,
  FileEditIcon,
  UserCircleIcon,
  Logout02Icon,
  Settings02Icon,
  ArrowDown01Icon,
} from "@/lib/icons"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
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

type IconType = typeof Dashboard02Icon

interface NavLeaf {
  type: "item"
  label: string
  path: string
  icon: IconType
  permission?: string
}

interface NavGroup {
  type: "group"
  id: string
  label: string
  icon: IconType
  children: NavLeaf[]
}

type NavEntry = NavLeaf | NavGroup

const NAV_ENTRIES: NavEntry[] = [
  {
    type: "item",
    label: "仪表盘",
    path: ROUTES.DASHBOARD,
    icon: Dashboard02Icon,
  },
  {
    type: "group",
    id: "system",
    label: "系统管理",
    icon: Settings02Icon,
    children: [
      {
        type: "item",
        label: "用户管理",
        path: ROUTES.USERS,
        icon: UserMultipleIcon,
        permission: PERMISSIONS.USER_READ,
      },
      {
        type: "item",
        label: "角色管理",
        path: ROUTES.ROLES,
        icon: Shield02Icon,
        permission: PERMISSIONS.ROLE_READ,
      },
      {
        type: "item",
        label: "权限管理",
        path: ROUTES.PERMISSIONS,
        icon: Key02Icon,
        permission: PERMISSIONS.PERMISSION_READ,
      },
    ],
  },
  {
    type: "item",
    label: "操作日志",
    path: ROUTES.AUDIT,
    icon: FileEditIcon,
    permission: PERMISSIONS.AUDIT_READ,
  },
]

function navLinkClassName(
  isActive: boolean,
  collapsed: boolean,
  nested = false
) {
  return cn(
    "flex items-center rounded-lg py-2 text-sm font-medium transition-colors",
    collapsed ? "justify-center px-2" : nested ? "gap-3 px-3 pl-9" : "gap-3 px-3",
    isActive
      ? "bg-primary text-primary-foreground"
      : "text-muted-foreground hover:bg-muted hover:text-foreground"
  )
}

function LeafLink({
  item,
  collapsed,
  nested,
  onNavigate,
}: {
  item: NavLeaf
  collapsed: boolean
  nested?: boolean
  onNavigate?: () => void
}) {
  const Icon = item.icon

  if (!collapsed) {
    return (
      <NavLink
        to={item.path}
        end
        onClick={onNavigate}
        className={({ isActive }) =>
          navLinkClassName(isActive, collapsed, nested)
        }
      >
        <Icon className="size-4 shrink-0" />
        <span>{item.label}</span>
      </NavLink>
    )
  }

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <NavLink
            to={item.path}
            end
            onClick={onNavigate}
            className={({ isActive }) =>
              navLinkClassName(isActive, collapsed, nested)
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
}

function GroupNav({
  group,
  collapsed,
  onNavigate,
}: {
  group: NavGroup
  collapsed: boolean
  onNavigate?: () => void
}) {
  const navigate = useNavigate()
  const location = useLocation()
  const GroupIcon = group.icon
  const childActive = group.children.some(
    (child) => location.pathname === child.path
  )
  const [open, setOpen] = useState(childActive)

  useEffect(() => {
    if (childActive) {
      setOpen(true)
    }
  }, [childActive])

  if (collapsed) {
    return (
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="ghost"
              className={cn(
                "h-auto w-full justify-center rounded-lg px-2 py-2",
                childActive
                  ? "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
              aria-label={group.label}
              title={group.label}
            />
          }
        >
          <GroupIcon />
        </DropdownMenuTrigger>
        <DropdownMenuContent
          side="right"
          align="start"
          sideOffset={8}
          className="w-44"
        >
          <DropdownMenuGroup>
            {group.children.map((child) => {
              const ChildIcon = child.icon
              return (
                <DropdownMenuItem
                  key={child.path}
                  onClick={() => {
                    navigate(child.path)
                    onNavigate?.()
                  }}
                >
                  <ChildIcon />
                  <span>{child.label}</span>
                </DropdownMenuItem>
              )
            })}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    )
  }

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger
        render={
          <Button
            variant="ghost"
            className={cn(
              "h-auto w-full justify-start gap-3 rounded-lg px-3 py-2 text-sm font-medium",
              childActive
                ? "text-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
          />
        }
      >
        <GroupIcon data-icon="inline-start" />
        <span className="flex-1 text-left">{group.label}</span>
        <ArrowDown01Icon
          data-icon="inline-end"
          className={cn("transition-transform", open && "rotate-180")}
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="flex flex-col gap-1 pt-1">
        {group.children.map((child) => (
          <LeafLink
            key={child.path}
            item={child}
            collapsed={false}
            nested
            onNavigate={onNavigate}
          />
        ))}
      </CollapsibleContent>
    </Collapsible>
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

  const entries = useMemo(() => {
    return NAV_ENTRIES.flatMap((entry): NavEntry[] => {
      if (entry.type === "item") {
        if (entry.permission && !hasPermission(entry.permission)) {
          return []
        }
        return [entry]
      }

      const children = entry.children.filter(
        (child) => !child.permission || hasPermission(child.permission)
      )
      if (children.length === 0) {
        return []
      }
      return [{ ...entry, children }]
    })
  }, [hasPermission])

  return (
    <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-3">
      {entries.map((entry) =>
        entry.type === "item" ? (
          <LeafLink
            key={entry.path}
            item={entry}
            collapsed={collapsed}
            onNavigate={onNavigate}
          />
        ) : (
          <GroupNav
            key={entry.id}
            group={entry}
            collapsed={collapsed}
            onNavigate={onNavigate}
          />
        )
      )}
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
            <DropdownMenuItem
              onClick={logout}
              variant="destructive"
              className="bg-destructive text-white focus:bg-destructive/90 focus:text-white data-[variant=destructive]:text-white data-[variant=destructive]:focus:bg-destructive/90 data-[variant=destructive]:focus:text-white data-[variant=destructive]:*:[svg]:text-white"
            >
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
          <NavList collapsed={false} onNavigate={() => onOpenChange(false)} />
          <UserMenu collapsed={false} />
        </SheetContent>
      </Sheet>
    </>
  )
}
