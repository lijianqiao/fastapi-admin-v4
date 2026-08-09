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

  const initials = user?.nickname?.charAt(0)?.toUpperCase() || user?.username?.charAt(0)?.toUpperCase() || "U"

  return (
    <header className="flex h-16 shrink-0 items-center gap-3 border-b bg-background px-4 md:px-6">
      {/* 移动端菜单按钮 */}
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        onClick={onMenuClick}
      >
        <Menu02Icon className="size-5" />
      </Button>

      <div className="flex-1" />

      {/* 主题切换 */}
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      >
        {theme === "dark" ? <Sun02Icon className="size-5" /> : <Moon02Icon className="size-5" />}
      </Button>

      <Separator orientation="vertical" className="h-6" />

      {/* 用户菜单 */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" className="gap-2 px-2">
            <Avatar className="size-8">
              <AvatarFallback className="bg-primary text-primary-foreground text-xs">
                {initials}
              </AvatarFallback>
            </Avatar>
            <span className="hidden text-sm font-medium md:inline">
              {user?.nickname || user?.username}
            </span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48">
          <DropdownMenuItem onClick={() => navigate(ROUTES.PROFILE)}>
            <UserCircleIcon className="size-4" />
            <span>个人中心</span>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={logout} className="text-destructive">
            <Logout02Icon className="size-4" />
            <span>退出登录</span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  )
}
