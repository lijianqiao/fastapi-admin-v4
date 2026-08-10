/** 角色回收站页

 * 列出软删除角色，支持恢复与永久删除。
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
import type { Role } from "@/types/role"

export function RolesTrashPage() {
  const [search, setSearch] = useState("")
  const [purgeOpen, setPurgeOpen] = useState(false)
  const [target, setTarget] = useState<Role | null>(null)

  const {
    items: roles,
    total,
    page,
    setPage,
    pageSize,
    isLoading,
    onPageSizeChange,
    refetch,
  } = usePaginatedQuery<Role>({
    url: "/roles/deleted",
    params: search ? { search } : {},
    errorMessage: "获取角色回收站失败",
  })

  const handleRestore = async (role: Role) => {
    try {
      await api.post(`/roles/${role.id}/restore`)
      toast.success("已恢复角色")
      refetch()
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } } }
      toast.error(error.response?.data?.message || "恢复失败")
    }
  }

  const handlePurgeConfirm = async (): Promise<boolean> => {
    if (!target) return false
    try {
      await api.delete(`/roles/${target.id}/purge`)
      toast.success("已永久删除")
      refetch()
      return true
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } } }
      toast.error(error.response?.data?.message || "永久删除失败")
      return false
    }
  }

  const columns = useMemo<ColumnDef<Role>[]>(
    () => [
      {
        accessorKey: "name",
        header: "角色名",
        cell: ({ row }) => (
          <span className="font-medium">{row.original.name}</span>
        ),
      },
      {
        accessorKey: "description",
        header: "描述",
        cell: ({ row }) => row.original.description || "-",
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
        title="角色回收站"
        description="恢复软删除角色，或永久删除以释放角色名占用"
        actions={
          <Button variant="outline" render={<Link to={ROUTES.ROLES} />}>
            返回角色管理
          </Button>
        }
      />

      <div className="mb-4">
        <Input
          placeholder="搜索角色名..."
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
        data={roles}
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
        description={`确定永久删除角色「${target?.name}」吗？此操作不可撤销，将释放角色名占用。`}
        onConfirm={handlePurgeConfirm}
      />
    </div>
  )
}
