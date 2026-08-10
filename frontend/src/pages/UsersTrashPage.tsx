/** 用户回收站页

 * 列出软删除用户，支持恢复与永久删除。
 */

import { useMemo, useState } from "react"
import { Link } from "react-router"
import type { ColumnDef } from "@tanstack/react-table"
import dayjs from "dayjs"
import { toast } from "sonner"

import { Delete02Icon, Tick02Icon } from "@/lib/icons"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/layout/PageHeader"
import { DataTable } from "@/components/common/DataTable"
import { Pagination } from "@/components/common/Pagination"
import { ConfirmDialog } from "@/components/common/ConfirmDialog"
import api from "@/lib/api"
import { usePaginatedQuery } from "@/hooks/use-paginated-query"
import { ROUTES } from "@/lib/constants"
import type { UserWithRoles } from "@/types/user"

export function UsersTrashPage() {
  const [search, setSearch] = useState("")
  const [purgeOpen, setPurgeOpen] = useState(false)
  const [target, setTarget] = useState<UserWithRoles | null>(null)

  const {
    items: users,
    total,
    page,
    setPage,
    pageSize,
    isLoading,
    onPageSizeChange,
    refetch,
  } = usePaginatedQuery<UserWithRoles>({
    url: "/users/deleted",
    params: search ? { search } : {},
    errorMessage: "获取用户回收站失败",
  })

  const handleRestore = async (user: UserWithRoles) => {
    try {
      await api.post(`/users/${user.id}/restore`)
      toast.success("已恢复用户")
      refetch()
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } } }
      toast.error(error.response?.data?.message || "恢复失败")
    }
  }

  const handlePurgeConfirm = async (): Promise<boolean> => {
    if (!target) return false
    try {
      await api.delete(`/users/${target.id}/purge`)
      toast.success("已永久删除")
      refetch()
      return true
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } } }
      toast.error(error.response?.data?.message || "永久删除失败")
      return false
    }
  }

  const columns = useMemo<ColumnDef<UserWithRoles>[]>(
    () => [
      {
        accessorKey: "username",
        header: "用户名",
        cell: ({ row }) => (
          <span className="font-medium">{row.original.username}</span>
        ),
      },
      {
        accessorKey: "email",
        header: "邮箱",
      },
      {
        accessorKey: "nickname",
        header: "昵称",
        cell: ({ row }) => row.original.nickname || "-",
      },
      {
        id: "roles",
        header: "角色",
        cell: ({ row }) => (
          <div className="flex flex-wrap gap-1">
            {row.original.roles?.map((role) => (
              <Badge key={role.id} variant="secondary">
                {role.name}
              </Badge>
            )) ?? <span className="text-muted-foreground">-</span>}
          </div>
        ),
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
        title="用户回收站"
        description="恢复软删除用户，或永久删除以释放用户名/邮箱占用"
        actions={
          <Button variant="outline" render={<Link to={ROUTES.USERS} />}>
            返回用户管理
          </Button>
        }
      />

      <div className="mb-4">
        <Input
          placeholder="搜索用户名或邮箱..."
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
        data={users}
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
        description={`确定永久删除用户「${target?.username}」吗？此操作不可撤销，将释放用户名与邮箱占用。`}
        onConfirm={handlePurgeConfirm}
      />
    </div>
  )
}
