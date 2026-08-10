/** 管理员重置用户密码对话框

 * 不需要旧密码；提交后目标用户的全部登录会话会被后端撤销。
 */

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
import type { User } from "@/types/user"

const schema = z
  .object({
    new_password: z.string().min(8, "密码至少 8 个字符").max(128),
    confirm_password: z.string().min(1, "请确认新密码"),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "两次输入的密码不一致",
    path: ["confirm_password"],
  })

type FormData = z.infer<typeof schema>

interface ResetPasswordDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  user: User | null
  onConfirm: (newPassword: string) => Promise<boolean>
}

export function ResetPasswordDialog({
  open,
  onOpenChange,
  user,
  onConfirm,
}: ResetPasswordDialogProps) {
  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { new_password: "", confirm_password: "" },
  })

  const handleOpenChange = (next: boolean) => {
    if (next) {
      form.reset({ new_password: "", confirm_password: "" })
    }
    onOpenChange(next)
  }

  const handleSubmit = async (data: FormData) => {
    const ok = await onConfirm(data.new_password)
    if (ok) handleOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>重置密码</DialogTitle>
          <DialogDescription>
            为用户「{user?.username}」设置新密码，无需知道原密码。重置后该用户的所有登录会话将被撤销。
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={form.handleSubmit(handleSubmit)}>
          <FieldGroup>
            <Controller
              control={form.control}
              name="new_password"
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor="reset-new-password">新密码</FieldLabel>
                  <Input
                    id="reset-new-password"
                    type="password"
                    autoComplete="new-password"
                    placeholder="至少 8 个字符"
                    aria-invalid={fieldState.invalid}
                    {...field}
                  />
                  <FieldError errors={[fieldState.error]} />
                </Field>
              )}
            />
            <Controller
              control={form.control}
              name="confirm_password"
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor="reset-confirm-password">
                    确认新密码
                  </FieldLabel>
                  <Input
                    id="reset-confirm-password"
                    type="password"
                    autoComplete="new-password"
                    placeholder="请再次输入新密码"
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
                onClick={() => handleOpenChange(false)}
                disabled={form.formState.isSubmitting}
              >
                取消
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting && (
                  <Spinner data-icon="inline-start" />
                )}
                确定重置
              </Button>
            </DialogFooter>
          </FieldGroup>
        </form>
      </DialogContent>
    </Dialog>
  )
}
