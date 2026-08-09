/** 404 页面未找到 */

import { useNavigate } from "react-router"

import { Button } from "@/components/ui/button"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty"
import { ROUTES } from "@/lib/constants"

export function NotFoundPage() {
  const navigate = useNavigate()

  return (
    <div className="flex h-svh items-center justify-center p-6">
      <Empty>
        <EmptyHeader>
          <EmptyTitle>404 页面不存在</EmptyTitle>
          <EmptyDescription>
            抱歉，您访问的页面不存在或已被移除。
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button onClick={() => navigate(ROUTES.DASHBOARD)}>返回首页</Button>
        </EmptyContent>
      </Empty>
    </div>
  )
}
