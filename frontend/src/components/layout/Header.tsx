/** 顶部栏

 * 包含移动端菜单、桌面端侧栏展开/收缩（位于侧栏与内容交界处），以及主题切换。
 */

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

interface HeaderProps {
  onMenuClick: () => void
  collapsed: boolean
  onCollapsedChange: (collapsed: boolean) => void
}

export function Header({
  onMenuClick,
  collapsed,
  onCollapsedChange,
}: HeaderProps) {
  const { theme, setTheme } = useTheme()

  return (
    <header className="flex h-16 shrink-0 items-center gap-3 border-b bg-background px-4 md:px-6">
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

      <div className="flex-1" />

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
