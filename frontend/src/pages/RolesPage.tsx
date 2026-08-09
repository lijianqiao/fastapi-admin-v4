/** 角色管理页

 * DataTable + 新增/编辑/删除/权限分配。
 */

import { useCallback, useEffect, useMemo, useState } from "react"
import type { ColumnDef } from "@tanstack/react-table"
import dayjs from "dayjs"
import { toast } from "sonner"

import {
  MoreHorizontalIcon,
  PlusSignIcon,
  PencilEdit02Icon,
  Delete02Icon,
  Key02Icon,
} from "@/lib/icons"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/layout/PageHeader"
import { DataTable } from "@/components/common/DataTable"
import { Pagination } from "@/components/common/Pagination"
import { ConfirmDialog } from "@/components/common/ConfirmDialog"
import { RoleFormDialog } from "@/components/roles/RoleFormDialog"
import { AssignPermissionsDialog } from "@/components/roles/AssignPermissionsDialog"
import api from "@/lib/api"
import { usePermission } from "@/hooks/use-permission"
import { PERMISSIONS } from "@/lib/constants"
import type { RoleCreate, RoleUpdate, RoleWithPermissions } from "@/types/role"

export function RolesPage() {
  const { hasPermission } = usePermission()
  const [roles, setRoles] = useState<RoleWithPermissions[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [search, setSearch] = useState("")
  const [isLoading, setIsLoading] = useState(true)

  const [formOpen, setFormOpen] = useState(false)
  const [editingRole, setEditingRole] = useState<RoleWithPermissions | null>(
    null
  )
  const [assignOpen, setAssignOpen] = useState(false)
  const [assignRole, setAssignRole] = useState<RoleWithPermissions | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteRole, setDeleteRole] = useState<RoleWithPermissions | null>(null)

  const fetchRoles = useCallback(async () => {
    setIsLoading(true)
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize }
      if (search) params.search = search
      const response = await api.get("/roles", { params })
      setRoles(response.data?.data?.items ?? [])
      setTotal(response.data?.data?.total ?? 0)
    } catch {
      toast.error("获取角色列表失败")
    } finally {
      setIsLoading(false)
    }
  }, [page, pageSize, search])

  useEffect(() => {
    fetchRoles()
  }, [fetchRoles])

  const handleSubmit = async (data: RoleCreate | RoleUpdate) => {
    try {
      if (editingRole) {
        await api.put(`/roles/${editingRole.id}`, data)
        toast.success("更新成功")
      } else {
        await api.post("/roles", data)
        toast.success("创建成功")
      }
      fetchRoles()
    } catch {
      toast.error(editingRole ? "更新失败" : "创建失败")
    }
  }

  const handleAssignConfirm = async (permissionIds: number[]) => {
    if (!assignRole) return
    try {
      await api.put(`/roles/${assignRole.id}/permissions`, {
        permission_ids: permissionIds,
      })
      toast.success("权限分配成功")
      fetchRoles()
    } catch {
      toast.error("权限分配失败")
    }
  }

  const handleDeleteConfirm = async () => {
    if (!deleteRole) return
    try {
      await api.delete(`/roles/${deleteRole.id}`)
      toast.success("删除成功")
      fetchRoles()
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } } }
      toast.error(error.response?.data?.message || "删除失败")
    }
    setDeleteOpen(false)
  }

  const columns = useMemo<ColumnDef<RoleWithPermissions>[]>(
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
        id: "permission_count",
        header: "权限数",
        cell: ({ row }) => (
          <Badge variant="secondary">
            {row.original.permissions?.length ?? 0}
          </Badge>
        ),
      },
      {
        id: "user_count",
        header: "关联用户",
        cell: ({ row }) => (
          <Badge variant="outline">{row.original.user_count ?? 0}</Badge>
        ),
      },
      {
        accessorKey: "created_at",
        header: "创建时间",
        cell: ({ row }) =>
          dayjs(row.original.created_at).format("YYYY-MM-DD HH:mm"),
      },
      {
        id: "actions",
        header: "操作",
        cell: ({ row }) => (
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button variant="ghost" size="icon-sm" aria-label="更多操作" />
              }
            >
              <MoreHorizontalIcon />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuGroup>
                {hasPermission(PERMISSIONS.ROLE_UPDATE) && (
                  <DropdownMenuItem
                    onClick={() => {
                      setEditingRole(row.original)
                      setFormOpen(true)
                    }}
                  >
                    <PencilEdit02Icon />
                    <span>编辑</span>
                  </DropdownMenuItem>
                )}
                {hasPermission(PERMISSIONS.ROLE_ASSIGN) && (
                  <DropdownMenuItem
                    onClick={() => {
                      setAssignRole(row.original)
                      setAssignOpen(true)
                    }}
                  >
                    <Key02Icon />
                    <span>分配权限</span>
                  </DropdownMenuItem>
                )}
                {hasPermission(PERMISSIONS.ROLE_DELETE) && (
                  <DropdownMenuItem
                    onClick={() => {
                      setDeleteRole(row.original)
                      setDeleteOpen(true)
                    }}
                    className="text-destructive"
                  >
                    <Delete02Icon />
                    <span>删除</span>
                  </DropdownMenuItem>
                )}
              </DropdownMenuGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        ),
      },
    ],
    [hasPermission]
  )

  return (
    <div>
      <PageHeader
        title="角色管理"
        description="管理系统角色和权限分配"
        actions={
          hasPermission(PERMISSIONS.ROLE_CREATE) && (
            <Button
              onClick={() => {
                setEditingRole(null)
                setFormOpen(true)
              }}
            >
              <PlusSignIcon data-icon="inline-start" />
              新增角色
            </Button>
          )
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
        emptyMessage="暂无角色数据"
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

      <RoleFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        role={editingRole}
        onSubmit={handleSubmit}
      />
      <AssignPermissionsDialog
        open={assignOpen}
        onOpenChange={setAssignOpen}
        role={assignRole}
        onConfirm={handleAssignConfirm}
      />
      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="确认删除角色"
        description={`确定要删除角色「${deleteRole?.name}」吗？如果该角色已关联用户，将无法删除。`}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  )
}
