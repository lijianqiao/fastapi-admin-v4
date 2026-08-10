/** 仪表盘页

 * 统计卡片 + 最近操作日志 + 快捷操作。
 */

import { useEffect, useState } from "react"
import { useNavigate } from "react-router"
import dayjs from "dayjs"
import { toast } from "sonner"

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
  const [loadError, setLoadError] = useState(false)

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true)
      setLoadError(false)
      try {
        const response = await api.get("/dashboard")
        setData(response.data?.data)
      } catch {
        setData(null)
        setLoadError(true)
        toast.error("获取仪表盘数据失败")
      } finally {
        setIsLoading(false)
      }
    }
    void fetchData()
  }, [])

  const stats = [
    {
      label: "用户总数",
      value: data?.stats.user_count,
      icon: UserMultipleIcon,
    },
    {
      label: "角色总数",
      value: data?.stats.role_count,
      icon: Shield02Icon,
    },
    {
      label: "权限总数",
      value: data?.stats.permission_count,
      icon: Key02Icon,
    },
    {
      label: "启用用户",
      value: data?.stats.active_user_count,
      icon: UserCheck02Icon,
    },
  ]

  return (
    <div>
      <PageHeader title="仪表盘" description="系统运行概览" />

      {loadError && !isLoading && (
        <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          仪表盘数据加载失败，请刷新页面重试。
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => {
          const Icon = stat.icon
          return (
            <Card key={stat.label}>
              <CardContent className="flex items-center gap-4">
                <div className="flex size-12 items-center justify-center rounded-lg bg-muted text-muted-foreground [&_svg]:size-6">
                  <Icon />
                </div>
                <div>
                  {isLoading ? (
                    <Skeleton className="h-8 w-16" />
                  ) : loadError ? (
                    <p className="text-2xl font-bold text-muted-foreground">—</p>
                  ) : (
                    <p className="text-2xl font-bold">{stat.value ?? 0}</p>
                  )}
                  <p className="text-sm text-muted-foreground">{stat.label}</p>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
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
            ) : loadError ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                无法加载操作记录
              </p>
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

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">快捷操作</CardTitle>
            <CardDescription>常用管理功能入口</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-3">
            <Button
              onClick={() => navigate(`${ROUTES.USERS}?create=1`)}
              variant="outline"
            >
              <PlusSignIcon data-icon="inline-start" />
              新增用户
            </Button>
            <Button
              onClick={() => navigate(`${ROUTES.ROLES}?create=1`)}
              variant="outline"
            >
              <PlusSignIcon data-icon="inline-start" />
              新增角色
            </Button>
            <Button
              onClick={() => navigate(`${ROUTES.PERMISSIONS}?create=1`)}
              variant="outline"
            >
              <PlusSignIcon data-icon="inline-start" />
              新增权限
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
