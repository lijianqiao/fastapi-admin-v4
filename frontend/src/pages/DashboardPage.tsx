/** 仪表盘页

 * 统计卡片 + 最近登录 + 快捷操作。
 */

import { useEffect, useState } from "react"
import { useNavigate } from "react-router"
import dayjs from "dayjs"

import {
  UserMultipleIcon,
  Shield02Icon,
  Key02Icon,
  UserCheck02Icon,
  PlusSignIcon,
} from "@/lib/icons"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { PageHeader } from "@/components/layout/PageHeader"
import api from "@/lib/api"
import { ROUTES } from "@/lib/constants"
import type { DashboardData } from "@/types/audit"

export function DashboardPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<DashboardData | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await api.get("/dashboard")
        setData(response.data?.data)
      } catch {
        // 忽略错误
      } finally {
        setIsLoading(false)
      }
    }
    fetchData()
  }, [])

  const stats = [
    {
      label: "用户总数",
      value: data?.stats.user_count ?? 0,
      icon: UserMultipleIcon,
    },
    {
      label: "角色总数",
      value: data?.stats.role_count ?? 0,
      icon: Shield02Icon,
    },
    {
      label: "权限总数",
      value: data?.stats.permission_count ?? 0,
      icon: Key02Icon,
    },
    {
      label: "启用用户",
      value: data?.stats.active_user_count ?? 0,
      icon: UserCheck02Icon,
    },
  ]

  return (
    <div>
      <PageHeader title="仪表盘" description="系统运行概览" />

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => {
          const Icon = stat.icon
          return (
            <Card key={stat.label}>
              <CardContent className="flex items-center gap-4">
                <div className="flex size-12 items-center justify-center rounded-2xl bg-muted text-muted-foreground [&_svg]:size-6">
                  <Icon />
                </div>
                <div>
                  {isLoading ? (
                    <Skeleton className="h-8 w-16" />
                  ) : (
                    <p className="text-2xl font-bold">{stat.value}</p>
                  )}
                  <p className="text-sm text-muted-foreground">{stat.label}</p>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* 最近登录 + 快捷操作 */}
      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* 最近登录 */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">最近操作日志</CardTitle>
            <CardDescription>最近 10 条系统操作记录</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex flex-col gap-2">
                {Array.from({ length: 5 }).map((_, index) => (
                  <Skeleton key={index} className="h-8 w-full" />
                ))}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead>用户</TableHead>
                    <TableHead>操作</TableHead>
                    <TableHead>IP</TableHead>
                    <TableHead>时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data?.recent_logs?.length ? (
                    data.recent_logs.map((log) => (
                      <TableRow key={log.id}>
                        <TableCell className="font-medium">
                          {log.username || "未知"}
                        </TableCell>
                        <TableCell>{log.action}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {log.ip || "-"}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {log.created_at
                            ? dayjs(log.created_at).format("MM-DD HH:mm")
                            : "-"}
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell
                        colSpan={4}
                        className="text-center text-muted-foreground"
                      >
                        暂无记录
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* 快捷操作 */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">快捷操作</CardTitle>
            <CardDescription>常用管理功能入口</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-3">
            <Button onClick={() => navigate(ROUTES.USERS)} variant="outline">
              <PlusSignIcon data-icon="inline-start" />
              新增用户
            </Button>
            <Button onClick={() => navigate(ROUTES.ROLES)} variant="outline">
              <PlusSignIcon data-icon="inline-start" />
              新增角色
            </Button>
            <Button
              onClick={() => navigate(ROUTES.PERMISSIONS)}
              variant="outline"
            >
              <PlusSignIcon data-icon="inline-start" />
              管理权限
            </Button>
            <Button onClick={() => navigate(ROUTES.AUDIT)} variant="outline">
              查看日志
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
