/** 404 页面未找到 */

import { useNavigate } from "react-router"

import { Button } from "@/components/ui/button"
import { ROUTES } from "@/lib/constants"

export function NotFoundPage() {
  const navigate = useNavigate()

  return (
    <div className="flex h-svh flex-col items-center justify-center gap-4 p-6">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-muted-foreground">404</h1>
        <p className="mt-4 text-muted-foreground">
          抱歉，您访问的页面不存在
        </p>
      </div>
      <Button onClick={() => navigate(ROUTES.DASHBOARD)}>
        返回首页
      </Button>
    </div>
  )
}
