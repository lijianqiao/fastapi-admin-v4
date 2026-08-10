/** 顶部栏

 * 包含移动端菜单、桌面端侧栏展开/收缩、当前页面包屑，以及主题切换。
 */

import { Fragment } from "react"
import { Link, useLocation } from "react-router"

import {
  Menu02Icon,
  Sun02Icon,
  Moon02Icon,
  PanelLeftIcon,
} from "@/lib/icons"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { useTheme } from "@/components/theme-provider"
import { ROUTES } from "@/lib/constants"

interface HeaderProps {
  onMenuClick: () => void
  collapsed: boolean
  onCollapsedChange: (collapsed: boolean) => void
}

interface Crumb {
  label: string
  path?: string
}

function getBreadcrumbs(pathname: string): Crumb[] {
  const map: Record<string, Crumb[]> = {
    [ROUTES.DASHBOARD]: [{ label: "仪表盘" }],
    [ROUTES.USERS]: [
      { label: "系统管理" },
      { label: "用户管理", path: ROUTES.USERS },
    ],
    [ROUTES.USERS_TRASH]: [
      { label: "系统管理" },
      { label: "用户管理", path: ROUTES.USERS },
      { label: "回收站" },
    ],
    [ROUTES.ROLES]: [
      { label: "系统管理" },
      { label: "角色管理", path: ROUTES.ROLES },
    ],
    [ROUTES.ROLES_TRASH]: [
      { label: "系统管理" },
      { label: "角色管理", path: ROUTES.ROLES },
      { label: "回收站" },
    ],
    [ROUTES.PERMISSIONS]: [
      { label: "系统管理" },
      { label: "权限管理", path: ROUTES.PERMISSIONS },
    ],
    [ROUTES.PERMISSIONS_TRASH]: [
      { label: "系统管理" },
      { label: "权限管理", path: ROUTES.PERMISSIONS },
      { label: "回收站" },
    ],
    [ROUTES.PROFILE]: [{ label: "个人中心" }],
    [ROUTES.AUDIT]: [{ label: "操作日志" }],
  }
  return map[pathname] ?? [{ label: "页面" }]
}

export function Header({
  onMenuClick,
  collapsed,
  onCollapsedChange,
}: HeaderProps) {
  const { theme, setTheme } = useTheme()
  const { pathname } = useLocation()
  const crumbs = getBreadcrumbs(pathname)

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b bg-background px-4 md:px-6">
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        aria-label="打开导航菜单"
        onClick={onMenuClick}
      >
        <Menu02Icon />
      </Button>

      <Tooltip>
        <TooltipTrigger
          render={
            <Button
              variant="ghost"
              size="icon"
              className="hidden md:inline-flex"
              aria-label={collapsed ? "展开侧边栏" : "收起侧边栏"}
              onClick={() => onCollapsedChange(!collapsed)}
            />
          }
        >
          <PanelLeftIcon />
        </TooltipTrigger>
        <TooltipContent side="bottom" sideOffset={6}>
          {collapsed ? "展开侧边栏" : "收起侧边栏"}
        </TooltipContent>
      </Tooltip>

      <nav
        aria-label="面包屑"
        className="flex min-w-0 flex-1 items-center gap-1.5 text-sm"
      >
        {crumbs.map((crumb, index) => {
          const isLast = index === crumbs.length - 1
          return (
            <Fragment key={`${crumb.label}-${index}`}>
              {index > 0 && (
                <span className="text-muted-foreground/60" aria-hidden>
                  /
                </span>
              )}
              {isLast || !crumb.path ? (
                <span
                  className={
                    isLast
                      ? "truncate font-medium text-foreground"
                      : "truncate text-muted-foreground"
                  }
                >
                  {crumb.label}
                </span>
              ) : (
                <Link
                  to={crumb.path}
                  className="truncate text-muted-foreground transition-colors hover:text-foreground"
                >
                  {crumb.label}
                </Link>
              )}
            </Fragment>
          )
        })}
      </nav>

      <Button
        variant="ghost"
        size="icon"
        aria-label={theme === "dark" ? "切换到浅色主题" : "切换到深色主题"}
        onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      >
        {theme === "dark" ? <Sun02Icon /> : <Moon02Icon />}
      </Button>
    </header>
  )
}
