/** 用户管理页

 * DataTable + 搜索/筛选 + 新增/编辑/删除/角色分配。
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
  UserAssign02Icon,
  ResetPasswordIcon,
  InboxIcon,
} from "@/lib/icons"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { useAuthStore } from "@/store/auth"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
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
import { ConfirmDialog } from "@/components/common/ConfirmDialog"
import { UserFormDialog } from "@/components/users/UserFormDialog"
import { AssignRolesDialog } from "@/components/users/AssignRolesDialog"
import { ResetPasswordDialog } from "@/components/users/ResetPasswordDialog"
import api from "@/lib/api"
import { usePaginatedQuery } from "@/hooks/use-paginated-query"
import { usePermission } from "@/hooks/use-permission"
import { PERMISSIONS, ROUTES } from "@/lib/constants"
import type { UserCreate, UserUpdate, UserWithRoles } from "@/types/user"

/** base-ui 的 Select 需要 items 才能在受控赋值时渲染选中项文案 */
const STATUS_ITEMS = [
  { label: "全部", value: "all" },
  { label: "启用", value: "active" },
  { label: "禁用", value: "inactive" },
]

export function UsersPage() {
  const { hasPermission } = usePermission()
  const [searchParams, setSearchParams] = useSearchParams()
  const currentUserId = useAuthStore((state) => state.user?.id)
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("all")

  const {
    items: users,
    total,
    page,
    setPage,
    pageSize,
    isLoading,
    onPageSizeChange,
    refetch: fetchUsers,
  } = usePaginatedQuery<UserWithRoles>({
    url: "/users",
    params: {
      ...(search ? { search } : {}),
      ...(statusFilter !== "all" ? { is_active: statusFilter === "active" } : {}),
    },
    errorMessage: "获取用户列表失败",
  })

  // Dialog 状态
  const [formOpen, setFormOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<UserWithRoles | null>(null)
  const [assignOpen, setAssignOpen] = useState(false)
  const [assignUser, setAssignUser] = useState<UserWithRoles | null>(null)
  const [resetPasswordOpen, setResetPasswordOpen] = useState(false)
  const [resetPasswordUser, setResetPasswordUser] =
    useState<UserWithRoles | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteUser, setDeleteUser] = useState<UserWithRoles | null>(null)

  const handleCreate = () => {
    setEditingUser(null)
    setFormOpen(true)
  }

  useEffect(() => {
    if (searchParams.get("create") === "1" && hasPermission(PERMISSIONS.USER_CREATE)) {
      setEditingUser(null)
      setFormOpen(true)
      const next = new URLSearchParams(searchParams)
      next.delete("create")
      setSearchParams(next, { replace: true })
    }
  }, [searchParams, setSearchParams, hasPermission])

  const handleEdit = (user: UserWithRoles) => {
    setEditingUser(user)
    setFormOpen(true)
  }

  const handleAssignRoles = (user: UserWithRoles) => {
    setAssignUser(user)
    setAssignOpen(true)
  }

  const handleResetPassword = (user: UserWithRoles) => {
    setResetPasswordUser(user)
    setResetPasswordOpen(true)
  }

  const handleDelete = (user: UserWithRoles) => {
    setDeleteUser(user)
    setDeleteOpen(true)
  }

  const handleSubmit = async (
    data: UserCreate | UserUpdate
  ): Promise<boolean> => {
    try {
      if (editingUser) {
        await api.put(`/users/${editingUser.id}`, data)
        toast.success("更新成功")
      } else {
        await api.post("/users", data)
        toast.success("创建成功")
      }
      fetchUsers()
      return true
    } catch {
      toast.error(editingUser ? "更新失败" : "创建失败")
      return false
    }
  }

  const handleAssignConfirm = async (roleIds: number[]): Promise<boolean> => {
    if (!assignUser) return false
    try {
      await api.put(`/users/${assignUser.id}/roles`, { role_ids: roleIds })
      toast.success("角色分配成功")
      fetchUsers()
      return true
    } catch {
      toast.error("角色分配失败")
      return false
    }
  }

  const handleResetPasswordConfirm = async (
    newPassword: string
  ): Promise<boolean> => {
    if (!resetPasswordUser) return false
    try {
      await api.put(`/users/${resetPasswordUser.id}/password`, {
        new_password: newPassword,
      })
      toast.success("密码重置成功")
      return true
    } catch {
      toast.error("密码重置失败")
      return false
    }
  }

  const handleDeleteConfirm = async (): Promise<boolean> => {
    if (!deleteUser) return false
    try {
      await api.delete(`/users/${deleteUser.id}`)
      toast.success("删除成功")
      fetchUsers()
      return true
    } catch {
      toast.error("删除失败")
      return false
    }
  }

  const handleToggleActive = useCallback(
    async (user: UserWithRoles, next: boolean) => {
      if (user.id === currentUserId && !next) {
        toast.error("不能停用当前登录用户")
        return
      }
      try {
        await api.put(`/users/${user.id}`, { is_active: next })
        toast.success(next ? "已启用用户" : "已禁用用户")
        fetchUsers()
      } catch (err: unknown) {
        const error = err as { response?: { data?: { message?: string } } }
        toast.error(error.response?.data?.message || "更新状态失败")
      }
    },
    [currentUserId, fetchUsers]
  )

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
        accessorKey: "is_active",
        header: "状态",
        cell: ({ row }) => {
          const user = row.original
          const canUpdate = hasPermission(PERMISSIONS.USER_UPDATE)
          if (!canUpdate) {
            return (
              <Badge variant={user.is_active ? "default" : "destructive"}>
                {user.is_active ? "启用" : "禁用"}
              </Badge>
            )
          }
          const isSelf = user.id === currentUserId
          return (
            <Switch
              checked={user.is_active}
              disabled={isSelf && user.is_active}
              onCheckedChange={(checked) => handleToggleActive(user, checked)}
              aria-label={
                isSelf && user.is_active
                  ? "不能停用当前登录用户"
                  : user.is_active
                    ? "禁用用户"
                    : "启用用户"
              }
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
                {hasPermission(PERMISSIONS.USER_UPDATE) && (
                  <DropdownMenuItem onClick={() => handleEdit(row.original)}>
                    <PencilEdit02Icon />
                    <span>编辑</span>
                  </DropdownMenuItem>
                )}
                {hasPermission(PERMISSIONS.USER_ASSIGN) && (
                  <DropdownMenuItem
                    onClick={() => handleAssignRoles(row.original)}
                  >
                    <UserAssign02Icon />
                    <span>分配角色</span>
                  </DropdownMenuItem>
                )}
                {hasPermission(PERMISSIONS.USER_RESET_PASSWORD) && (
                  <DropdownMenuItem
                    onClick={() => handleResetPassword(row.original)}
                  >
                    <ResetPasswordIcon />
                    <span>重置密码</span>
                  </DropdownMenuItem>
                )}
                {hasPermission(PERMISSIONS.USER_DELETE) && (
                  <DropdownMenuItem
                    onClick={() => handleDelete(row.original)}
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
    [hasPermission, currentUserId, handleToggleActive]
  )

  return (
    <div>
      <PageHeader
        title="用户管理"
        description="管理系统中的用户"
        actions={
          <>
            {hasPermission(PERMISSIONS.USER_DELETE) && (
              <Button
                variant="outline"
                render={<Link to={ROUTES.USERS_TRASH} />}
              >
                <InboxIcon data-icon="inline-start" />
                回收站
              </Button>
            )}
            {hasPermission(PERMISSIONS.USER_CREATE) && (
              <Button onClick={handleCreate}>
                <PlusSignIcon data-icon="inline-start" />
                新增用户
              </Button>
            )}
          </>
        }
      />

      {/* 工具栏 */}
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          placeholder="搜索用户名或邮箱..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
          className="sm:max-w-xs"
        />
        <Select
          items={STATUS_ITEMS}
          value={statusFilter}
          onValueChange={(value) => {
            setStatusFilter(value ?? "all")
            setPage(1)
          }}
        >
          <SelectTrigger className="sm:w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {STATUS_ITEMS.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>

      {/* 数据表格 */}
      <DataTable
        columns={columns}
        data={users}
        isLoading={isLoading}
        emptyMessage="暂无用户数据"
      />

      {/* 分页 */}
      <Pagination
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={setPage}
        onPageSizeChange={onPageSizeChange}
      />

      {/* 对话框 */}
      <UserFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        user={editingUser}
        onSubmit={handleSubmit}
      />
      <AssignRolesDialog
        open={assignOpen}
        onOpenChange={setAssignOpen}
        user={assignUser}
        onConfirm={handleAssignConfirm}
      />
      <ResetPasswordDialog
        open={resetPasswordOpen}
        onOpenChange={setResetPasswordOpen}
        user={resetPasswordUser}
        onConfirm={handleResetPasswordConfirm}
      />
      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="确认删除用户"
        description={`确定要删除用户「${deleteUser?.username}」吗？此操作不可撤销。`}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  )
}
