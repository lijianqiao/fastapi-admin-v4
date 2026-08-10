/** 权限回收站页

 * 列出软删除权限，支持恢复与永久删除。
 */

import { useMemo, useState } from "react"
import { Link } from "react-router"
import type { ColumnDef } from "@tanstack/react-table"
import dayjs from "dayjs"
import { toast } from "sonner"

import { Delete02Icon, Tick02Icon } from "@/lib/icons"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/layout/PageHeader"
import { DataTable } from "@/components/common/DataTable"
import { Pagination } from "@/components/common/Pagination"
import { ConfirmDialog } from "@/components/common/ConfirmDialog"
import api from "@/lib/api"
import { usePaginatedQuery } from "@/hooks/use-paginated-query"
import { ROUTES } from "@/lib/constants"
import type { Permission } from "@/types/permission"

export function PermissionsTrashPage() {
  const [search, setSearch] = useState("")
  const [purgeOpen, setPurgeOpen] = useState(false)
  const [target, setTarget] = useState<Permission | null>(null)

  const {
    items: permissions,
    total,
    page,
    setPage,
    pageSize,
    isLoading,
    onPageSizeChange,
    refetch,
  } = usePaginatedQuery<Permission>({
    url: "/permissions/deleted",
    params: search ? { search } : {},
    errorMessage: "获取权限回收站失败",
  })

  const handleRestore = async (permission: Permission) => {
    try {
      await api.post(`/permissions/${permission.id}/restore`)
      toast.success("已恢复权限")
      refetch()
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } } }
      toast.error(error.response?.data?.message || "恢复失败")
    }
  }

  const handlePurgeConfirm = async (): Promise<boolean> => {
    if (!target) return false
    try {
      await api.delete(`/permissions/${target.id}/purge`)
      toast.success("已永久删除")
      refetch()
      return true
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } } }
      toast.error(error.response?.data?.message || "永久删除失败")
      return false
    }
  }

  const columns = useMemo<ColumnDef<Permission>[]>(
    () => [
      {
        accessorKey: "name",
        header: "权限名称",
        cell: ({ row }) => (
          <span className="font-medium">{row.original.name}</span>
        ),
      },
      {
        accessorKey: "code",
        header: "权限码",
        cell: ({ row }) => (
          <code className="rounded bg-muted px-1.5 py-0.5 text-sm">
            {row.original.code}
          </code>
        ),
      },
      {
        accessorKey: "module",
        header: "模块",
        cell: ({ row }) => row.original.module || "-",
      },
      {
        accessorKey: "updated_at",
        header: "删除时间",
        cell: ({ row }) =>
          dayjs(row.original.updated_at).format("YYYY-MM-DD HH:mm"),
      },
      {
        id: "actions",
        header: "操作",
        cell: ({ row }) => (
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleRestore(row.original)}
            >
              <Tick02Icon data-icon="inline-start" />
              恢复
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => {
                setTarget(row.original)
                setPurgeOpen(true)
              }}
            >
              <Delete02Icon data-icon="inline-start" />
              永久删除
            </Button>
          </div>
        ),
      },
    ],
    []
  )

  return (
    <div>
      <PageHeader
        title="权限回收站"
        description="恢复软删除权限，或永久删除以释放权限码占用"
        actions={
          <Button variant="outline" render={<Link to={ROUTES.PERMISSIONS} />}>
            返回权限管理
          </Button>
        }
      />

      <div className="mb-4">
        <Input
          placeholder="搜索权限名或代码..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
          className="sm:max-w-xs"
        />
      </div>

      <DataTable
        columns={columns}
        data={permissions}
        isLoading={isLoading}
        emptyMessage="回收站为空"
      />

      <Pagination
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={setPage}
        onPageSizeChange={onPageSizeChange}
      />

      <ConfirmDialog
        open={purgeOpen}
        onOpenChange={setPurgeOpen}
        title="确认永久删除"
        description={`确定永久删除权限「${target?.code}」吗？此操作不可撤销，将释放权限码占用。`}
        onConfirm={handlePurgeConfirm}
      />
    </div>
  )
}
