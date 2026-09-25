/** 审计日志页

 * DataTable + 筛选。
 */

import { useMemo, useState } from "react"
import type { ColumnDef } from "@tanstack/react-table"
import dayjs from "dayjs"

import {
  AUDIT_ACTION_LABELS,
  AuditLogDrawer,
  auditActionLabel,
} from "@/components/audit/AuditLogDrawer"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
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
import { ViewIcon } from "@/lib/icons"
import type { AuditLog } from "@/types/audit"

/** base-ui 的 Select 需要 items 才能在受控赋值时渲染选中项文案 */
const ACTION_ITEMS = [
  { label: "全部操作", value: "all" },
  ...Object.entries(AUDIT_ACTION_LABELS).map(([value, label]) => ({
    label,
    value,
  })),
]

/** 与后端 CRUDAuditLog.count_cap 一致 */
const AUDIT_COUNT_CAP = 10000

export function AuditLogsPage() {
  const [actionFilter, setActionFilter] = useState<string>("all")
  const [searchUsername, setSearchUsername] = useState("")
  const [previewLog, setPreviewLog] = useState<AuditLog | null>(null)

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
            {auditActionLabel(row.original.action)}
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
          <span className="block max-w-56 truncate text-sm text-muted-foreground">
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
      {
        id: "preview",
        header: "",
        cell: ({ row }) => (
          <Button
            type="button"
            variant="outline"
            size="sm"
            aria-label={`预览 ${auditActionLabel(row.original.action)} 日志`}
            onClick={() => setPreviewLog(row.original)}
          >
            <ViewIcon />
            预览
          </Button>
        ),
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
        maxTotal={AUDIT_COUNT_CAP}
      />

      <AuditLogDrawer log={previewLog} onClose={() => setPreviewLog(null)} />
    </div>
  )
}
