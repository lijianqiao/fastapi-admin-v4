/** 用户管理页

 * DataTable + 搜索/筛选 + 新增/编辑/删除/角色分配。
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
  UserAssign02Icon,
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
import api from "@/lib/api"
import { usePermission } from "@/hooks/use-permission"
import { PERMISSIONS } from "@/lib/constants"
import type { UserCreate, UserUpdate, UserWithRoles } from "@/types/user"

/** base-ui 的 Select 需要 items 才能在受控赋值时渲染选中项文案 */
const STATUS_ITEMS = [
  { label: "全部", value: "all" },
  { label: "启用", value: "active" },
  { label: "禁用", value: "inactive" },
]

export function UsersPage() {
  const { hasPermission } = usePermission()
  const [users, setUsers] = useState<UserWithRoles[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [isLoading, setIsLoading] = useState(true)

  // Dialog 状态
  const [formOpen, setFormOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<UserWithRoles | null>(null)
  const [assignOpen, setAssignOpen] = useState(false)
  const [assignUser, setAssignUser] = useState<UserWithRoles | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteUser, setDeleteUser] = useState<UserWithRoles | null>(null)

  const fetchUsers = useCallback(async () => {
    setIsLoading(true)
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize }
      if (search) params.search = search
      if (statusFilter !== "all") params.is_active = statusFilter === "active"

      const response = await api.get("/users", { params })
      setUsers(response.data?.data?.items ?? [])
      setTotal(response.data?.data?.total ?? 0)
    } catch {
      toast.error("获取用户列表失败")
    } finally {
      setIsLoading(false)
    }
  }, [page, pageSize, search, statusFilter])

  useEffect(() => {
    fetchUsers()
  }, [fetchUsers])

  const handleCreate = () => {
    setEditingUser(null)
    setFormOpen(true)
  }

  const handleEdit = (user: UserWithRoles) => {
    setEditingUser(user)
    setFormOpen(true)
  }

  const handleAssignRoles = (user: UserWithRoles) => {
    setAssignUser(user)
    setAssignOpen(true)
  }

  const handleDelete = (user: UserWithRoles) => {
    setDeleteUser(user)
    setDeleteOpen(true)
  }

  const handleSubmit = async (data: UserCreate | UserUpdate) => {
    try {
      if (editingUser) {
        await api.put(`/users/${editingUser.id}`, data)
        toast.success("更新成功")
      } else {
        await api.post("/users", data)
        toast.success("创建成功")
      }
      fetchUsers()
    } catch {
      toast.error(editingUser ? "更新失败" : "创建失败")
    }
  }

  const handleAssignConfirm = async (roleIds: number[]) => {
    if (!assignUser) return
    try {
      await api.put(`/users/${assignUser.id}/roles`, { role_ids: roleIds })
      toast.success("角色分配成功")
      fetchUsers()
    } catch {
      toast.error("角色分配失败")
    }
  }

  const handleDeleteConfirm = async () => {
    if (!deleteUser) return
    try {
      await api.delete(`/users/${deleteUser.id}`)
      toast.success("删除成功")
      fetchUsers()
    } catch {
      toast.error("删除失败")
    }
    setDeleteOpen(false)
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
        accessorKey: "is_active",
        header: "状态",
        cell: ({ row }) => (
          <Badge variant={row.original.is_active ? "default" : "destructive"}>
            {row.original.is_active ? "启用" : "禁用"}
          </Badge>
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
    [hasPermission]
  )

  return (
    <div>
      <PageHeader
        title="用户管理"
        description="管理系统中的用户"
        actions={
          hasPermission(PERMISSIONS.USER_CREATE) && (
            <Button onClick={handleCreate}>
              <PlusSignIcon data-icon="inline-start" />
              新增用户
            </Button>
          )
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
        onPageSizeChange={(size) => {
          setPageSize(size)
          setPage(1)
        }}
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
