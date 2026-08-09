/** 审计日志页

 * DataTable + 筛选。
 */

import { useCallback, useEffect, useMemo, useState } from "react"
import type { ColumnDef } from "@tanstack/react-table"
import dayjs from "dayjs"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { PageHeader } from "@/components/layout/PageHeader"
import { DataTable } from "@/components/common/DataTable"
import { Pagination } from "@/components/common/Pagination"
import api from "@/lib/api"
import type { AuditLog } from "@/types/audit"

const ACTION_LABELS: Record<string, string> = {
  register: "注册",
  login: "登录",
  logout: "退出",
  create_user: "创建用户",
  update_user: "更新用户",
  delete_user: "删除用户",
  assign_roles: "分配角色",
  create_role: "创建角色",
  update_role: "更新角色",
  delete_role: "删除角色",
  assign_permissions: "分配权限",
  create_permission: "创建权限",
  update_permission: "更新权限",
  delete_permission: "删除权限",
  update_profile: "更新资料",
  change_password: "修改密码",
}

export function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [actionFilter, setActionFilter] = useState<string>("all")
  const [searchUserId, setSearchUserId] = useState("")
  const [isLoading, setIsLoading] = useState(true)

  const fetchLogs = useCallback(async () => {
    setIsLoading(true)
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize }
      if (actionFilter !== "all") params.action = actionFilter
      if (searchUserId) params.user_id = Number(searchUserId)

      const response = await api.get("/audit-logs", { params })
      setLogs(response.data?.data?.items ?? [])
      setTotal(response.data?.data?.total ?? 0)
    } catch {
      toast.error("获取审计日志失败")
    } finally {
      setIsLoading(false)
    }
  }, [page, pageSize, actionFilter, searchUserId])

  useEffect(() => {
    fetchLogs()
  }, [fetchLogs])

  const columns = useMemo<ColumnDef<AuditLog>[]>(
    () => [
      {
        accessorKey: "username",
        header: "用户",
        cell: ({ row }) => (
          <span className="font-medium">{row.original.username || "未知"}</span>
        ),
      },
      {
        accessorKey: "action",
        header: "操作",
        cell: ({ row }) => (
          <Badge variant="outline">
            {ACTION_LABELS[row.original.action] ?? row.original.action}
          </Badge>
        ),
      },
      {
        accessorKey: "target",
        header: "目标",
        cell: ({ row }) => (
          <span className="font-mono text-sm text-muted-foreground">
            {row.original.target || "-"}
          </span>
        ),
      },
      {
        accessorKey: "detail",
        header: "详情",
        cell: ({ row }) => (
          <span className="text-sm text-muted-foreground">
            {row.original.detail || "-"}
          </span>
        ),
      },
      {
        accessorKey: "ip",
        header: "IP 地址",
        cell: ({ row }) => (
          <span className="font-mono text-sm">{row.original.ip || "-"}</span>
        ),
      },
      {
        accessorKey: "created_at",
        header: "时间",
        cell: ({ row }) =>
          dayjs(row.original.created_at).format("YYYY-MM-DD HH:mm:ss"),
      },
    ],
    [],
  )

  return (
    <div>
      <PageHeader title="操作日志" description="查看系统操作记录" />

      {/* 工具栏 */}
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          placeholder="按用户 ID 筛选..."
          value={searchUserId}
          onChange={(e) => {
            setSearchUserId(e.target.value)
            setPage(1)
          }}
          className="sm:max-w-xs"
        />
        <Select
          value={actionFilter}
          onValueChange={(val) => {
            setActionFilter(val)
            setPage(1)
          }}
        >
          <SelectTrigger className="sm:w-40">
            <SelectValue placeholder="操作类型" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部操作</SelectItem>
            {Object.entries(ACTION_LABELS).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <DataTable
        columns={columns}
        data={logs}
        isLoading={isLoading}
        emptyMessage="暂无日志记录"
      />

      <Pagination
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={setPage}
        onPageSizeChange={(size) => {
          setPageSize(size)
          setPage(1)
        }}
      />
    </div>
  )
}
