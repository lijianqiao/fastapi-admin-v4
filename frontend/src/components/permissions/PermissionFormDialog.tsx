/** 权限新增/编辑表单对话框 */

import { useEffect } from "react"
import { Controller, useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import type {
  Permission,
  PermissionCreate,
  PermissionUpdate,
} from "@/types/permission"

const schema = z.object({
  name: z.string().min(1, "请输入权限名称").max(100),
  code: z.string().min(1, "请输入权限码").max(100),
  module: z.string().max(50).optional().default(""),
  description: z.string().max(500).optional().default(""),
})

type FormData = z.infer<typeof schema>

interface PermissionFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  permission?: Permission | null
  onSubmit: (data: PermissionCreate | PermissionUpdate) => Promise<boolean>
}

export function PermissionFormDialog({
  open,
  onOpenChange,
  permission,
  onSubmit,
}: PermissionFormDialogProps) {
  const isEdit = !!permission

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", code: "", module: "", description: "" },
  })

  useEffect(() => {
    if (open) {
      form.reset({
        name: permission?.name ?? "",
        code: permission?.code ?? "",
        module: permission?.module ?? "",
        description: permission?.description ?? "",
      })
    }
  }, [open, permission, form])

  const handleSubmit = async (data: FormData) => {
    const ok = await onSubmit(data)
    if (ok) onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? "编辑权限" : "新增权限"}</DialogTitle>
          <DialogDescription>
            {isEdit ? "修改权限信息" : "创建一个新的权限定义"}
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
                  <FieldLabel htmlFor="permission-module">所属模块</FieldLabel>
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
                onClick={() => onOpenChange(false)}
                disabled={form.formState.isSubmitting}
              >
                取消
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting && (
                  <Spinner data-icon="inline-start" />
                )}
                确定
              </Button>
            </DialogFooter>
          </FieldGroup>
        </form>
      </DialogContent>
    </Dialog>
  )
}
