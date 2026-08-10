/** 权限管理页

 * DataTable + 模块筛选 + 新增/编辑/删除/状态开关。
 */

import { useCallback, useEffect, useMemo, useState } from "react"
import { Link, useSearchParams } from "react-router"
import type { ColumnDef } from "@tanstack/react-table"
import dayjs from "dayjs"
import { toast } from "sonner"

import {
  PlusSignIcon,
  PencilEdit02Icon,
  Delete02Icon,
  MoreHorizontalIcon,
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
import { PermissionFormDialog } from "@/components/permissions/PermissionFormDialog"
import api from "@/lib/api"
import { usePaginatedQuery } from "@/hooks/use-paginated-query"
import { usePermission } from "@/hooks/use-permission"
import { PERMISSIONS, ROUTES } from "@/lib/constants"
import type {
  GroupedPermissions,
  Permission,
  PermissionCreate,
  PermissionUpdate,
} from "@/types/permission"

export function PermissionsPage() {
  const { hasPermission } = usePermission()
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState("")
  const [moduleFilter, setModuleFilter] = useState<string>("all")
  const [moduleNames, setModuleNames] = useState<string[]>([])

  const {
    items: permissions,
    total,
    page,
    setPage,
    pageSize,
    isLoading,
    onPageSizeChange,
    refetch: fetchPermissions,
  } = usePaginatedQuery<Permission>({
    url: "/permissions",
    params: {
      ...(search ? { search } : {}),
      ...(moduleFilter !== "all" ? { module: moduleFilter } : {}),
    },
    initialPageSize: 20,
    errorMessage: "获取权限列表失败",
  })

  const [formOpen, setFormOpen] = useState(false)
  const [editingPerm, setEditingPerm] = useState<Permission | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deletePerm, setDeletePerm] = useState<Permission | null>(null)

  useEffect(() => {
    const loadModules = async () => {
      try {
        const response = await api.get("/permissions", {
          params: { grouped: true },
        })
        const grouped = (response.data?.data ?? {}) as GroupedPermissions
        setModuleNames(Object.keys(grouped))
      } catch {
        // 模块筛选项加载失败时不影响主列表
      }
    }
    void loadModules()
  }, [])

  useEffect(() => {
    if (searchParams.get("create") === "1" && hasPermission(PERMISSIONS.PERMISSION_CREATE)) {
      setEditingPerm(null)
      setFormOpen(true)
      const next = new URLSearchParams(searchParams)
      next.delete("create")
      setSearchParams(next, { replace: true })
    }
  }, [searchParams, setSearchParams, hasPermission])

  const moduleItems = [
    { label: "全部模块", value: "all" },
    ...moduleNames.map((mod) => ({ label: mod, value: mod })),
  ]

  const handleCreate = () => {
    setEditingPerm(null)
    setFormOpen(true)
  }

  const handleEdit = (perm: Permission) => {
    setEditingPerm(perm)
    setFormOpen(true)
  }

  const handleSubmit = async (
    data: PermissionCreate | PermissionUpdate
  ): Promise<boolean> => {
    try {
      if (editingPerm) {
        await api.put(`/permissions/${editingPerm.id}`, data)
        toast.success("更新成功")
      } else {
        await api.post("/permissions", data)
        toast.success("创建成功")
      }
      fetchPermissions()
      return true
    } catch {
      toast.error(editingPerm ? "更新失败" : "创建失败")
      return false
    }
  }

  const handleDeleteConfirm = async (): Promise<boolean> => {
    if (!deletePerm) return false
    try {
      await api.delete(`/permissions/${deletePerm.id}`)
      toast.success("删除成功")
      fetchPermissions()
      return true
    } catch {
      toast.error("删除失败")
      return false
    }
  }

  const handleToggleActive = useCallback(
    async (perm: Permission, next: boolean) => {
      try {
        await api.put(`/permissions/${perm.id}`, { is_active: next })
        toast.success(next ? "已启用权限" : "已禁用权限")
        fetchPermissions()
      } catch {
        toast.error("更新状态失败")
      }
    },
    [fetchPermissions]
  )

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
        accessorKey: "description",
        header: "描述",
        cell: ({ row }) => row.original.description || "-",
      },
      {
        accessorKey: "is_active",
        header: "状态",
        cell: ({ row }) => {
          const perm = row.original
          if (!hasPermission(PERMISSIONS.PERMISSION_UPDATE)) {
            return (
              <Badge variant={perm.is_active ? "default" : "destructive"}>
                {perm.is_active ? "启用" : "禁用"}
              </Badge>
            )
          }
          return (
            <Switch
              checked={perm.is_active}
              onCheckedChange={(checked) => handleToggleActive(perm, checked)}
              aria-label={perm.is_active ? "禁用权限" : "启用权限"}
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
                {hasPermission(PERMISSIONS.PERMISSION_UPDATE) && (
                  <DropdownMenuItem onClick={() => handleEdit(row.original)}>
                    <PencilEdit02Icon />
                    <span>编辑</span>
                  </DropdownMenuItem>
                )}
                {hasPermission(PERMISSIONS.PERMISSION_DELETE) && (
                  <DropdownMenuItem
                    onClick={() => {
                      setDeletePerm(row.original)
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
        title="权限管理"
        description="管理系统权限定义"
        actions={
          <>
            {hasPermission(PERMISSIONS.PERMISSION_DELETE) && (
              <Button
                variant="outline"
                render={<Link to={ROUTES.PERMISSIONS_TRASH} />}
              >
                <InboxIcon data-icon="inline-start" />
                回收站
              </Button>
            )}
            {hasPermission(PERMISSIONS.PERMISSION_CREATE) && (
              <Button onClick={handleCreate}>
                <PlusSignIcon data-icon="inline-start" />
                新增权限
              </Button>
            )}
          </>
        }
      />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          placeholder="搜索权限名或代码..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
          className="sm:max-w-xs"
        />
        <Select
          items={moduleItems}
          value={moduleFilter}
          onValueChange={(value) => {
            setModuleFilter(value ?? "all")
            setPage(1)
          }}
        >
          <SelectTrigger className="sm:w-40" aria-label="模块筛选">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {moduleItems.map((item) => (
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
        data={permissions}
        isLoading={isLoading}
        emptyMessage="暂无权限数据"
      />

      <Pagination
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={setPage}
        onPageSizeChange={onPageSizeChange}
      />

      <PermissionFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        permission={editingPerm}
        onSubmit={handleSubmit}
      />

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="确认删除权限"
        description={`确定要删除权限「${deletePerm?.code}」吗？`}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  )
}
