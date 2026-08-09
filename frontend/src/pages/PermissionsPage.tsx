/** 权限管理页

 * 按模块分组展示权限 + 新增/编辑/删除。
 */

import { useCallback, useEffect, useState } from "react"
import dayjs from "dayjs"
import { toast } from "sonner"

import {
  PlusSignIcon,
  PencilEdit02Icon,
  Delete02Icon,
  Key02Icon,
  MoreHorizontalIcon,
} from "@/lib/icons"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { PageHeader } from "@/components/layout/PageHeader"
import { ConfirmDialog } from "@/components/common/ConfirmDialog"
import api from "@/lib/api"
import { usePermission } from "@/hooks/use-permission"
import { PERMISSIONS } from "@/lib/constants"
import type { GroupedPermissions, Permission } from "@/types/permission"

import { Controller, useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"

const schema = z.object({
  name: z.string().min(1, "请输入权限名称").max(100),
  code: z.string().min(1, "请输入权限码").max(100),
  module: z.string().max(50).optional().default(""),
  description: z.string().max(500).optional().default(""),
})

type FormData = z.infer<typeof schema>

export function PermissionsPage() {
  const { hasPermission } = usePermission()
  const [grouped, setGrouped] = useState<GroupedPermissions>({})
  const [search, setSearch] = useState("")
  const [moduleFilter, setModuleFilter] = useState<string>("all")
  const [isLoading, setIsLoading] = useState(true)

  const [formOpen, setFormOpen] = useState(false)
  const [editingPerm, setEditingPerm] = useState<Permission | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deletePerm, setDeletePerm] = useState<Permission | null>(null)

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", code: "", module: "", description: "" },
  })

  const fetchPermissions = useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await api.get("/permissions", {
        params: { grouped: true, page_size: 200 },
      })
      setGrouped(response.data?.data ?? {})
    } catch {
      toast.error("获取权限列表失败")
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPermissions()
  }, [fetchPermissions])

  // base-ui 的 Select 需要 items 才能在受控赋值时渲染选中项文案
  const moduleItems = [
    { label: "全部模块", value: "all" },
    ...Object.keys(grouped).map((mod) => ({ label: mod, value: mod })),
  ]

  const filteredGrouped: GroupedPermissions = (() => {
    const result: GroupedPermissions = {}
    for (const [mod, perms] of Object.entries(grouped)) {
      if (moduleFilter !== "all" && mod !== moduleFilter) continue
      const filtered = perms.filter((p) => {
        if (!search) return true
        const s = search.toLowerCase()
        return (
          p.name.toLowerCase().includes(s) || p.code.toLowerCase().includes(s)
        )
      })
      if (filtered.length > 0) {
        result[mod] = filtered
      }
    }
    return result
  })()

  const handleCreate = () => {
    setEditingPerm(null)
    form.reset({ name: "", code: "", module: "", description: "" })
    setFormOpen(true)
  }

  const handleEdit = (perm: Permission) => {
    setEditingPerm(perm)
    form.reset({
      name: perm.name,
      code: perm.code,
      module: perm.module,
      description: perm.description,
    })
    setFormOpen(true)
  }

  const handleSubmit = async (data: FormData) => {
    try {
      if (editingPerm) {
        await api.put(`/permissions/${editingPerm.id}`, data)
        toast.success("更新成功")
      } else {
        await api.post("/permissions", data)
        toast.success("创建成功")
      }
      fetchPermissions()
    } catch {
      toast.error(editingPerm ? "更新失败" : "创建失败")
    }
    setFormOpen(false)
  }

  const handleDeleteConfirm = async () => {
    if (!deletePerm) return
    try {
      await api.delete(`/permissions/${deletePerm.id}`)
      toast.success("删除成功")
      fetchPermissions()
    } catch {
      toast.error("删除失败")
    }
    setDeleteOpen(false)
  }

  return (
    <div>
      <PageHeader
        title="权限管理"
        description="管理系统权限定义"
        actions={
          hasPermission(PERMISSIONS.PERMISSION_CREATE) && (
            <Button onClick={handleCreate}>
              <PlusSignIcon data-icon="inline-start" />
              新增权限
            </Button>
          )
        }
      />

      {/* 工具栏 */}
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          placeholder="搜索权限名或代码..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="sm:max-w-xs"
        />
        <Select
          items={moduleItems}
          value={moduleFilter}
          onValueChange={(value) => setModuleFilter(value ?? "all")}
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

      {/* 按模块分组展示 */}
      {isLoading ? (
        <div className="flex flex-col gap-4">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-40 w-full" />
          ))}
        </div>
      ) : Object.keys(filteredGrouped).length === 0 ? (
        <Empty className="border">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Key02Icon />
            </EmptyMedia>
            <EmptyTitle>暂无权限数据</EmptyTitle>
            <EmptyDescription>
              {search || moduleFilter !== "all"
                ? "没有匹配当前筛选条件的权限，请调整搜索词或模块。"
                : "系统还没有定义任何权限，先创建一个权限定义。"}
            </EmptyDescription>
          </EmptyHeader>
          {hasPermission(PERMISSIONS.PERMISSION_CREATE) && (
            <EmptyContent>
              <Button onClick={handleCreate}>
                <PlusSignIcon data-icon="inline-start" />
                新增权限
              </Button>
            </EmptyContent>
          )}
        </Empty>
      ) : (
        <div className="flex flex-col gap-4">
          {Object.entries(filteredGrouped).map(([moduleName, perms]) => (
            <Card key={moduleName}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  {moduleName}
                  <Badge variant="secondary">{perms.length}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow className="hover:bg-transparent">
                      <TableHead>权限名称</TableHead>
                      <TableHead>权限码</TableHead>
                      <TableHead>描述</TableHead>
                      <TableHead>创建时间</TableHead>
                      <TableHead className="w-20">操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {perms.map((perm) => (
                      <TableRow key={perm.id}>
                        <TableCell className="font-medium">
                          {perm.name}
                        </TableCell>
                        <TableCell>
                          <code className="rounded bg-muted px-1.5 py-0.5 text-sm">
                            {perm.code}
                          </code>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {perm.description || "-"}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {dayjs(perm.created_at).format("YYYY-MM-DD")}
                        </TableCell>
                        <TableCell>
                          <DropdownMenu>
                            <DropdownMenuTrigger
                              render={
                                <Button
                                  variant="ghost"
                                  size="icon-sm"
                                  aria-label="更多操作"
                                />
                              }
                            >
                              <MoreHorizontalIcon />
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuGroup>
                                {hasPermission(
                                  PERMISSIONS.PERMISSION_UPDATE
                                ) && (
                                  <DropdownMenuItem
                                    onClick={() => handleEdit(perm)}
                                  >
                                    <PencilEdit02Icon />
                                    <span>编辑</span>
                                  </DropdownMenuItem>
                                )}
                                {hasPermission(
                                  PERMISSIONS.PERMISSION_DELETE
                                ) && (
                                  <DropdownMenuItem
                                    onClick={() => {
                                      setDeletePerm(perm)
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
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* 新增/编辑对话框 */}
      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{editingPerm ? "编辑权限" : "新增权限"}</DialogTitle>
            <DialogDescription>
              {editingPerm ? "修改权限信息" : "创建一个新的权限定义"}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={form.handleSubmit(handleSubmit)}>
            <FieldGroup>
              <Controller
                control={form.control}
                name="name"
                render={({ field, fieldState }) => (
                  <Field data-invalid={fieldState.invalid}>
                    <FieldLabel htmlFor="permission-name">权限名称</FieldLabel>
                    <Input
                      id="permission-name"
                      placeholder="如：查看用户"
                      aria-invalid={fieldState.invalid}
                      {...field}
                    />
                    <FieldError errors={[fieldState.error]} />
                  </Field>
                )}
              />
              <Controller
                control={form.control}
                name="code"
                render={({ field, fieldState }) => (
                  <Field data-invalid={fieldState.invalid}>
                    <FieldLabel htmlFor="permission-code">权限码</FieldLabel>
                    <Input
                      id="permission-code"
                      placeholder="如：user:read"
                      className="font-mono"
                      aria-invalid={fieldState.invalid}
                      {...field}
                    />
                    <FieldDescription>
                      格式为 <code>模块:动作</code>，如 <code>user:read</code>。
                    </FieldDescription>
                    <FieldError errors={[fieldState.error]} />
                  </Field>
                )}
              />
              <Controller
                control={form.control}
                name="module"
                render={({ field, fieldState }) => (
                  <Field data-invalid={fieldState.invalid}>
                    <FieldLabel htmlFor="permission-module">
                      所属模块
                    </FieldLabel>
                    <Input
                      id="permission-module"
                      placeholder="如：用户管理"
                      aria-invalid={fieldState.invalid}
                      {...field}
                    />
                    <FieldError errors={[fieldState.error]} />
                  </Field>
                )}
              />
              <Controller
                control={form.control}
                name="description"
                render={({ field, fieldState }) => (
                  <Field data-invalid={fieldState.invalid}>
                    <FieldLabel htmlFor="permission-description">
                      描述
                    </FieldLabel>
                    <Textarea
                      id="permission-description"
                      placeholder="权限描述（选填）"
                      className="resize-none"
                      aria-invalid={fieldState.invalid}
                      {...field}
                    />
                    <FieldError errors={[fieldState.error]} />
                  </Field>
                )}
              />
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setFormOpen(false)}
                >
                  取消
                </Button>
                <Button type="submit">确定</Button>
              </DialogFooter>
            </FieldGroup>
          </form>
        </DialogContent>
      </Dialog>

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
