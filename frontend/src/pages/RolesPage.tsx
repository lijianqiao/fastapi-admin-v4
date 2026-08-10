/** 角色管理页

 * DataTable + 新增/编辑/删除/权限分配。
 */

import { useCallback, useEffect, useMemo, useState } from "react"
import { Link, useSearchParams } from "react-router"
import type { ColumnDef } from "@tanstack/react-table"
import dayjs from "dayjs"
import { toast } from "sonner"

import {
  MoreHorizontalIcon,
  PlusSignIcon,
  PencilEdit02Icon,
  Delete02Icon,
  Key02Icon,
  InboxIcon,
} from "@/lib/icons"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
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
import { usePaginatedQuery } from "@/hooks/use-paginated-query"
import { usePermission } from "@/hooks/use-permission"
import { PERMISSIONS, ROUTES } from "@/lib/constants"
import type { RoleCreate, RoleUpdate, RoleWithPermissions } from "@/types/role"

export function RolesPage() {
  const { hasPermission } = usePermission()
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState("")

  const {
    items: roles,
    total,
    page,
    setPage,
    pageSize,
    isLoading,
    onPageSizeChange,
    refetch: fetchRoles,
  } = usePaginatedQuery<RoleWithPermissions>({
    url: "/roles",
    params: search ? { search } : {},
    errorMessage: "获取角色列表失败",
  })

  const [formOpen, setFormOpen] = useState(false)
  const [editingRole, setEditingRole] = useState<RoleWithPermissions | null>(
    null
  )
  const [assignOpen, setAssignOpen] = useState(false)
  const [assignRole, setAssignRole] = useState<RoleWithPermissions | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteRole, setDeleteRole] = useState<RoleWithPermissions | null>(null)

  useEffect(() => {
    if (searchParams.get("create") === "1" && hasPermission(PERMISSIONS.ROLE_CREATE)) {
      setEditingRole(null)
      setFormOpen(true)
      const next = new URLSearchParams(searchParams)
      next.delete("create")
      setSearchParams(next, { replace: true })
    }
  }, [searchParams, setSearchParams, hasPermission])

  const handleSubmit = async (
    data: RoleCreate | RoleUpdate
  ): Promise<boolean> => {
    try {
      if (editingRole) {
        await api.put(`/roles/${editingRole.id}`, data)
        toast.success("更新成功")
      } else {
        await api.post("/roles", data)
        toast.success("创建成功")
      }
      fetchRoles()
      return true
    } catch {
      toast.error(editingRole ? "更新失败" : "创建失败")
      return false
    }
  }

  const handleAssignConfirm = async (
    permissionIds: number[]
  ): Promise<boolean> => {
    if (!assignRole) return false
    try {
      await api.put(`/roles/${assignRole.id}/permissions`, {
        permission_ids: permissionIds,
      })
      toast.success("权限分配成功")
      fetchRoles()
      return true
    } catch {
      toast.error("权限分配失败")
      return false
    }
  }

  const handleDeleteConfirm = async (): Promise<boolean> => {
    if (!deleteRole) return false
    try {
      await api.delete(`/roles/${deleteRole.id}`)
      toast.success("删除成功")
      fetchRoles()
      return true
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } } }
      toast.error(error.response?.data?.message || "删除失败")
      return false
    }
  }

  const handleToggleActive = useCallback(
    async (role: RoleWithPermissions, next: boolean) => {
      try {
        await api.put(`/roles/${role.id}`, { is_active: next })
        toast.success(next ? "已启用角色" : "已禁用角色")
        fetchRoles()
      } catch {
        toast.error("更新状态失败")
      }
    },
    [fetchRoles]
  )

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
        accessorKey: "is_active",
        header: "状态",
        cell: ({ row }) => {
          const role = row.original
          const canUpdate = hasPermission(PERMISSIONS.ROLE_UPDATE)
          if (!canUpdate) {
            return (
              <Badge variant={role.is_active ? "default" : "destructive"}>
                {role.is_active ? "启用" : "禁用"}
              </Badge>
            )
          }
          return (
            <Switch
              checked={role.is_active}
              onCheckedChange={(checked) => handleToggleActive(role, checked)}
              aria-label={role.is_active ? "禁用角色" : "启用角色"}
            />
          )
        },
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
    [hasPermission, handleToggleActive]
  )

  return (
    <div>
      <PageHeader
        title="角色管理"
        description="管理系统角色和权限分配"
        actions={
          <>
            {hasPermission(PERMISSIONS.ROLE_DELETE) && (
              <Button
                variant="outline"
                render={<Link to={ROUTES.ROLES_TRASH} />}
              >
                <InboxIcon data-icon="inline-start" />
                回收站
              </Button>
            )}
            {hasPermission(PERMISSIONS.ROLE_CREATE) && (
              <Button
                onClick={() => {
                  setEditingRole(null)
                  setFormOpen(true)
                }}
              >
                <PlusSignIcon data-icon="inline-start" />
                新增角色
              </Button>
            )}
          </>
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
        onPageSizeChange={onPageSizeChange}
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
