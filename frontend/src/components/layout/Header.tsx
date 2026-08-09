/** 顶部栏

 * 包含移动端菜单按钮、面包屑、用户下拉菜单。
 */

import { useNavigate } from "react-router"

import {
  UserCircleIcon,
  Logout02Icon,
  Menu02Icon,
  Sun02Icon,
  Moon02Icon,
} from "@/lib/icons"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu"
import { Separator } from "@/components/ui/separator"
import { useAuth } from "@/hooks/use-auth"
import { useTheme } from "@/components/theme-provider"
import { ROUTES } from "@/lib/constants"

interface HeaderProps {
  onMenuClick: () => void
}

export function Header({ onMenuClick }: HeaderProps) {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const { theme, setTheme } = useTheme()

  const initials =
    user?.nickname?.charAt(0)?.toUpperCase() ||
    user?.username?.charAt(0)?.toUpperCase() ||
    "U"

  return (
    <header className="flex h-16 shrink-0 items-center gap-3 border-b bg-background px-4 md:px-6">
      {/* 移动端菜单按钮 */}
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        aria-label="打开导航菜单"
        onClick={onMenuClick}
      >
        <Menu02Icon />
      </Button>

      <div className="flex-1" />

      {/* 主题切换 */}
      <Button
        variant="ghost"
        size="icon"
        aria-label={theme === "dark" ? "切换到浅色主题" : "切换到深色主题"}
        onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      >
        {theme === "dark" ? <Sun02Icon /> : <Moon02Icon />}
      </Button>

      <Separator orientation="vertical" />

      {/* 用户菜单 */}
      <DropdownMenu>
        <DropdownMenuTrigger
          render={<Button variant="ghost" className="gap-2 px-2" />}
        >
          <Avatar className="size-8">
            <AvatarFallback className="text-xs">{initials}</AvatarFallback>
          </Avatar>
          <span className="hidden text-sm font-medium md:inline">
            {user?.nickname || user?.username}
          </span>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48">
          <DropdownMenuGroup>
            <DropdownMenuItem onClick={() => navigate(ROUTES.PROFILE)}>
              <UserCircleIcon />
              <span>个人中心</span>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={logout} className="text-destructive">
              <Logout02Icon />
              <span>退出登录</span>
            </DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  )
}
