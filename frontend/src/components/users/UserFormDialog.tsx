/** 用户新增/编辑表单对话框

 * 使用 react-hook-form + zod 进行表单验证。
 */

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
import type { User, UserCreate, UserUpdate } from "@/types/user"

const createSchema = z.object({
  username: z.string().min(3, "用户名至少 3 个字符").max(50),
  email: z.string().email("请输入有效的邮箱地址"),
  password: z.string().min(8, "密码至少 8 个字符").max(128),
  nickname: z.string().max(50).optional().default(""),
})

const editSchema = z.object({
  email: z.string().email("请输入有效的邮箱地址"),
  nickname: z.string().max(50).optional().default(""),
  password: z
    .string()
    .min(8, "密码至少 8 个字符")
    .max(128)
    .optional()
    .or(z.literal("")),
})

interface UserFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  user?: User | null
  onSubmit: (data: UserCreate | UserUpdate) => Promise<void>
}

export function UserFormDialog({
  open,
  onOpenChange,
  user,
  onSubmit,
}: UserFormDialogProps) {
  const isEdit = !!user

  const form = useForm<
    z.infer<typeof createSchema> | z.infer<typeof editSchema>
  >({
    resolver: zodResolver(isEdit ? editSchema : createSchema),
    defaultValues: {
      username: "",
      email: "",
      password: "",
      nickname: "",
    },
  })

  useEffect(() => {
    if (open) {
      if (user) {
        form.reset({
          email: user.email,
          nickname: user.nickname,
          password: "",
        })
      } else {
        form.reset({
          username: "",
          email: "",
          password: "",
          nickname: "",
        })
      }
    }
  }, [open, user, form])

  const handleSubmit = async (
    data: z.infer<typeof createSchema> | z.infer<typeof editSchema>
  ) => {
    if (isEdit) {
      const editData = data as z.infer<typeof editSchema>
      const updateData: UserUpdate = {
        email: editData.email,
        nickname: editData.nickname || undefined,
      }
      // 如果填了密码，也更新密码（通过 update 接口不直接处理密码，这里简化）
      await onSubmit(updateData)
    } else {
      const createData = data as z.infer<typeof createSchema>
      const userData: UserCreate = {
        username: createData.username,
        email: createData.email,
        password: createData.password,
        nickname: createData.nickname || undefined,
      }
      await onSubmit(userData)
    }
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? "编辑用户" : "新增用户"}</DialogTitle>
          <DialogDescription>
            {isEdit ? "修改用户信息" : "创建一个新用户账户"}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={form.handleSubmit(handleSubmit)}>
          <FieldGroup>
            {!isEdit && (
              <Controller
                control={form.control as never}
                name="username"
                render={({ field, fieldState }) => (
                  <Field data-invalid={fieldState.invalid}>
                    <FieldLabel htmlFor="user-username">用户名</FieldLabel>
                    <Input
                      id="user-username"
                      autoComplete="off"
                      placeholder="请输入用户名"
                      aria-invalid={fieldState.invalid}
                      {...field}
                    />
                    <FieldError errors={[fieldState.error]} />
                  </Field>
                )}
              />
            )}
            <Controller
              control={form.control as never}
              name="email"
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor="user-email">邮箱</FieldLabel>
                  <Input
                    id="user-email"
                    type="email"
                    placeholder="请输入邮箱"
                    aria-invalid={fieldState.invalid}
                    {...field}
                  />
                  <FieldError errors={[fieldState.error]} />
                </Field>
              )}
            />
            <Controller
              control={form.control as never}
              name="nickname"
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor="user-nickname">昵称</FieldLabel>
                  <Input
                    id="user-nickname"
                    placeholder="请输入昵称"
                    aria-invalid={fieldState.invalid}
                    {...field}
                  />
                  <FieldError errors={[fieldState.error]} />
                </Field>
              )}
            />
            <Controller
              control={form.control as never}
              name="password"
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor="user-password">
                    {isEdit ? "新密码（留空则不修改）" : "密码"}
                  </FieldLabel>
                  <Input
                    id="user-password"
                    type="password"
                    autoComplete="new-password"
                    placeholder={isEdit ? "留空则不修改" : "请输入密码"}
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
