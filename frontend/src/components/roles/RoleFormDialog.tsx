/** 角色新增/编辑表单对话框 */

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
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import type { Role, RoleCreate, RoleUpdate } from "@/types/role"

const schema = z.object({
  name: z.string().min(1, "请输入角色名").max(50),
  description: z.string().max(500).optional().default(""),
})

type FormData = z.infer<typeof schema>

interface RoleFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  role?: Role | null
  onSubmit: (data: RoleCreate | RoleUpdate) => Promise<void>
}

export function RoleFormDialog({
  open,
  onOpenChange,
  role,
  onSubmit,
}: RoleFormDialogProps) {
  const isEdit = !!role

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "",
      description: "",
    },
  })

  useEffect(() => {
    if (open) {
      form.reset({
        name: role?.name ?? "",
        description: role?.description ?? "",
      })
    }
  }, [open, role, form])

  const handleSubmit = async (data: FormData) => {
    if (isEdit) {
      await onSubmit({
        name: data.name,
        description: data.description || undefined,
      } as RoleUpdate)
    } else {
      await onSubmit({
        name: data.name,
        description: data.description || undefined,
      } as RoleCreate)
    }
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? "编辑角色" : "新增角色"}</DialogTitle>
          <DialogDescription>
            {isEdit ? "修改角色信息" : "创建一个新角色"}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={form.handleSubmit(handleSubmit)}>
          <FieldGroup>
            <Controller
              control={form.control}
              name="name"
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor="role-name">角色名称</FieldLabel>
                  <Input
                    id="role-name"
                    placeholder="请输入角色名称"
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
                  <FieldLabel htmlFor="role-description">描述</FieldLabel>
                  <Textarea
                    id="role-description"
                    placeholder="请输入角色描述（选填）"
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
              >
                取消
              </Button>
              <Button type="submit">确定</Button>
            </DialogFooter>
          </FieldGroup>
        </form>
      </DialogContent>
    </Dialog>
  )
}
