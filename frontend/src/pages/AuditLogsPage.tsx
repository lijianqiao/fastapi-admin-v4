/** 审计日志页

 * DataTable + 筛选。
 */

import { useMemo, useState } from "react"
import type { ColumnDef } from "@tanstack/react-table"
import dayjs from "dayjs"

import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { PageHeader } from "@/components/layout/PageHeader"
import { DataTable } from "@/components/common/DataTable"
import { Pagination } from "@/components/common/Pagination"
import { usePaginatedQuery } from "@/hooks/use-paginated-query"
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
  restore_user: "恢复用户",
  purge_user: "永久删除用户",
  restore_role: "恢复角色",
  purge_role: "永久删除角色",
  restore_permission: "恢复权限",
  purge_permission: "永久删除权限",
  update_profile: "更新资料",
  change_password: "修改密码",
  reset_password: "重置密码",
}

/** base-ui 的 Select 需要 items 才能在受控赋值时渲染选中项文案 */
const ACTION_ITEMS = [
  { label: "全部操作", value: "all" },
  ...Object.entries(ACTION_LABELS).map(([value, label]) => ({ label, value })),
]

export function AuditLogsPage() {
  const [actionFilter, setActionFilter] = useState<string>("all")
  const [searchUsername, setSearchUsername] = useState("")

  const {
    items: logs,
    total,
    page,
    setPage,
    pageSize,
    isLoading,
    onPageSizeChange,
  } = usePaginatedQuery<AuditLog>({
    url: "/audit-logs",
    params: {
      ...(actionFilter !== "all" ? { action: actionFilter } : {}),
      ...(searchUsername ? { username: searchUsername } : {}),
    },
    initialPageSize: 20,
    errorMessage: "获取审计日志失败",
  })

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
    []
  )

  return (
    <div>
      <PageHeader title="操作日志" description="查看系统操作记录" />

      {/* 工具栏 */}
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          placeholder="按用户名筛选..."
          value={searchUsername}
          onChange={(e) => {
            setSearchUsername(e.target.value)
            setPage(1)
          }}
          className="sm:max-w-xs"
        />
        <Select
          items={ACTION_ITEMS}
          value={actionFilter}
          onValueChange={(value) => {
            setActionFilter(value ?? "all")
            setPage(1)
          }}
        >
          <SelectTrigger className="sm:w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {ACTION_ITEMS.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectGroup>
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
        onPageSizeChange={onPageSizeChange}
      />
    </div>
  )
}
