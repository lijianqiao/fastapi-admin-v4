/** 用户新增/编辑表单对话框

 * 新增和编辑分别使用独立的 useForm 实例，避免联合类型下的类型断言。
 * 密码不在此处修改，重置密码是独立的管理员操作，见 ResetPasswordDialog。
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
import { Spinner } from "@/components/ui/spinner"
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
})

interface UserFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  user?: User | null
  onSubmit: (data: UserCreate | UserUpdate) => Promise<boolean>
}

function CreateUserForm({
  onOpenChange,
  onSubmit,
}: {
  onOpenChange: (open: boolean) => void
  onSubmit: (data: UserCreate) => Promise<boolean>
}) {
  const form = useForm<z.infer<typeof createSchema>>({
    resolver: zodResolver(createSchema),
    defaultValues: { username: "", email: "", password: "", nickname: "" },
  })

  const handleSubmit = async (data: z.infer<typeof createSchema>) => {
    const ok = await onSubmit({
      username: data.username,
      email: data.email,
      password: data.password,
      nickname: data.nickname || undefined,
    })
    if (ok) onOpenChange(false)
  }

  return (
    <form onSubmit={form.handleSubmit(handleSubmit)}>
      <FieldGroup>
        <Controller
          control={form.control}
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
        <Controller
          control={form.control}
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
          control={form.control}
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
          control={form.control}
          name="password"
          render={({ field, fieldState }) => (
            <Field data-invalid={fieldState.invalid}>
              <FieldLabel htmlFor="user-password">密码</FieldLabel>
              <Input
                id="user-password"
                type="password"
                autoComplete="new-password"
                placeholder="请输入密码"
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
  )
}

function EditUserForm({
  user,
  onOpenChange,
  onSubmit,
}: {
  user: User
  onOpenChange: (open: boolean) => void
  onSubmit: (data: UserUpdate) => Promise<boolean>
}) {
  const form = useForm<z.infer<typeof editSchema>>({
    resolver: zodResolver(editSchema),
    defaultValues: { email: user.email, nickname: user.nickname },
  })

  useEffect(() => {
    form.reset({ email: user.email, nickname: user.nickname })
  }, [user, form])

  const handleSubmit = async (data: z.infer<typeof editSchema>) => {
    const ok = await onSubmit({
      email: data.email,
      nickname: data.nickname || undefined,
    })
    if (ok) onOpenChange(false)
  }

  return (
    <form onSubmit={form.handleSubmit(handleSubmit)}>
      <FieldGroup>
        <Controller
          control={form.control}
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
          control={form.control}
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
  )
}

export function UserFormDialog({
  open,
  onOpenChange,
  user,
  onSubmit,
}: UserFormDialogProps) {
  const isEdit = !!user

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? "编辑用户" : "新增用户"}</DialogTitle>
          <DialogDescription>
            {isEdit ? "修改用户信息" : "创建一个新用户账户"}
          </DialogDescription>
        </DialogHeader>
        {isEdit && user ? (
          <EditUserForm
            key={user.id}
            user={user}
            onOpenChange={onOpenChange}
            onSubmit={onSubmit}
          />
        ) : (
          <CreateUserForm
            key="create"
            onOpenChange={onOpenChange}
            onSubmit={onSubmit}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
