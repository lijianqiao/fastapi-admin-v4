/** 403 禁止访问页面 */

import { useNavigate } from "react-router"

import { Cancel01Icon } from "@/lib/icons"
import { Button } from "@/components/ui/button"
import { ROUTES } from "@/lib/constants"

export function ForbiddenPage() {
  const navigate = useNavigate()

  return (
    <div className="flex h-svh flex-col items-center justify-center gap-4 p-6">
      <div className="flex size-20 items-center justify-center rounded-full bg-destructive/10">
        <Cancel01Icon className="size-10 text-destructive" />
      </div>
      <div className="text-center">
        <h1 className="text-4xl font-bold">403</h1>
        <p className="mt-2 text-muted-foreground">
          抱歉，您没有权限访问此页面
        </p>
      </div>
      <Button onClick={() => navigate(ROUTES.DASHBOARD)}>
        返回首页
      </Button>
    </div>
  )
}
