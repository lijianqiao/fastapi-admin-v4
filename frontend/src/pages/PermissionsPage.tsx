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
} from "@/lib/icons"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
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
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
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
import type {
  GroupedPermissions,
  Permission,
} from "@/types/permission"

import { useForm } from "react-hook-form"
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

  const modules = Object.keys(grouped)

  const filteredGrouped: GroupedPermissions = (() => {
    const result: GroupedPermissions = {}
    for (const [mod, perms] of Object.entries(grouped)) {
      if (moduleFilter !== "all" && mod !== moduleFilter) continue
      const filtered = perms.filter((p) => {
        if (!search) return true
        const s = search.toLowerCase()
        return (
          p.name.toLowerCase().includes(s) ||
          p.code.toLowerCase().includes(s)
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
              <PlusSignIcon className="size-4" />
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
          value={moduleFilter}
          onValueChange={setModuleFilter}
        >
          <SelectTrigger className="sm:w-40">
            <SelectValue placeholder="模块筛选" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部模块</SelectItem>
            {modules.map((mod) => (
              <SelectItem key={mod} value={mod}>
                {mod}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* 按模块分组展示 */}
      {isLoading ? (
        <div className="text-center text-muted-foreground">加载中...</div>
      ) : Object.keys(filteredGrouped).length === 0 ? (
        <div className="rounded-lg border p-8 text-center text-muted-foreground">
          暂无权限数据
        </div>
      ) : (
        <div className="space-y-4">
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
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon-sm">
                                <PencilEdit02Icon className="size-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              {hasPermission(PERMISSIONS.PERMISSION_UPDATE) && (
                                <DropdownMenuItem
                                  onClick={() => handleEdit(perm)}
                                >
                                  <PencilEdit02Icon className="size-4" />
                                  <span>编辑</span>
                                </DropdownMenuItem>
                              )}
                              {hasPermission(PERMISSIONS.PERMISSION_DELETE) && (
                                <DropdownMenuItem
                                  onClick={() => {
                                    setDeletePerm(perm)
                                    setDeleteOpen(true)
                                  }}
                                  className="text-destructive"
                                >
                                  <Delete02Icon className="size-4" />
                                  <span>删除</span>
                                </DropdownMenuItem>
                              )}
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
            <DialogTitle>
              {editingPerm ? "编辑权限" : "新增权限"}
            </DialogTitle>
            <DialogDescription>
              {editingPerm ? "修改权限信息" : "创建一个新的权限定义"}
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(handleSubmit)}
              className="space-y-4"
            >
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>权限名称</FormLabel>
                    <FormControl>
                      <Input placeholder="如：查看用户" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="code"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>权限码</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="如：user:read"
                        className="font-mono"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="module"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>所属模块</FormLabel>
                    <FormControl>
                      <Input placeholder="如：用户管理" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>描述</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="权限描述（选填）"
                        className="resize-none"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
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
            </form>
          </Form>
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
