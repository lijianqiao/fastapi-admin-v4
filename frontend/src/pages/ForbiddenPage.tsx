/** 403 禁止访问页面 */

import { useNavigate } from "react-router"

import { Cancel01Icon } from "@/lib/icons"
import { Button } from "@/components/ui/button"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { ROUTES } from "@/lib/constants"

export function ForbiddenPage() {
  const navigate = useNavigate()

  return (
    <div className="flex h-svh items-center justify-center p-6">
      <Empty>
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <Cancel01Icon />
          </EmptyMedia>
          <EmptyTitle>403 无访问权限</EmptyTitle>
          <EmptyDescription>
            抱歉，您没有权限访问此页面。如需访问请联系管理员分配相应角色。
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button onClick={() => navigate(ROUTES.DASHBOARD)}>返回首页</Button>
        </EmptyContent>
      </Empty>
    </div>
  )
}
