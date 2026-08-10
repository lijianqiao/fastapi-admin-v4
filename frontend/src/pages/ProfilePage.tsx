/** 个人中心页

 * 个人信息编辑 + 修改密码。
 */

import { useEffect, useState } from "react"
import { Controller, useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import dayjs from "dayjs"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldTitle,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { PageHeader } from "@/components/layout/PageHeader"
import api from "@/lib/api"
import { useAuthStore } from "@/store/auth"
import type { CurrentUser } from "@/types/user"

const profileSchema = z.object({
  nickname: z.string().max(50).optional().default(""),
  email: z.string().email("请输入有效的邮箱地址"),
})

type ProfileFormData = z.infer<typeof profileSchema>

const passwordSchema = z
  .object({
    old_password: z.string().min(1, "请输入旧密码"),
    new_password: z.string().min(8, "新密码至少 8 个字符").max(128),
    confirm_password: z.string().min(1, "请确认新密码"),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "两次输入的密码不一致",
    path: ["confirm_password"],
  })

type PasswordFormData = z.infer<typeof passwordSchema>

function getPasswordStrength(password: string): number {
  let strength = 0
  if (password.length >= 8) strength += 25
  if (password.length >= 12) strength += 25
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) strength += 25
  if (/\d/.test(password) && /[^A-Za-z0-9]/.test(password)) strength += 25
  return strength
}

export function ProfilePage() {
  const { user, setUser } = useAuthStore()
  const [profile, setProfile] = useState<CurrentUser | null>(user)

  const profileForm = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: { nickname: "", email: "" },
  })

  const passwordForm = useForm<PasswordFormData>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { old_password: "", new_password: "", confirm_password: "" },
  })

  const [newPassword, setNewPassword] = useState("")

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await api.get("/me")
        const data: CurrentUser = response.data?.data
        if (data) {
          setProfile(data)
          profileForm.reset({
            nickname: data.nickname,
            email: data.email,
          })
        }
      } catch {
        // 忽略
      }
    }
    fetchProfile()
  }, [profileForm])

  const handleProfileSubmit = async (data: ProfileFormData) => {
    try {
      const response = await api.put("/me", {
        nickname: data.nickname || undefined,
        email: data.email,
      })
      const updated = response.data?.data
      if (updated) {
        setProfile(updated)
        setUser(updated)
      }
      toast.success("个人信息更新成功")
    } catch {
      toast.error("更新失败")
    }
  }

  const handlePasswordSubmit = async (data: PasswordFormData) => {
    try {
      await api.put("/me/password", {
        old_password: data.old_password,
        new_password: data.new_password,
      })
      toast.success("密码修改成功")
      passwordForm.reset()
      setNewPassword("")
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } } }
      toast.error(error.response?.data?.message || "密码修改失败")
    }
  }

  const passwordStrength = getPasswordStrength(newPassword)

  return (
    <div>
      <PageHeader title="个人中心" description="管理个人信息和密码" />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* 个人信息 */}
        <Card>
          <CardHeader>
            <CardTitle>个人信息</CardTitle>
            <CardDescription>修改您的个人资料</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={profileForm.handleSubmit(handleProfileSubmit)}>
              <FieldGroup>
                <Field data-disabled>
                  <FieldLabel htmlFor="profile-username">用户名</FieldLabel>
                  <Input
                    id="profile-username"
                    value={profile?.username ?? ""}
                    disabled
                  />
                  <FieldDescription>用户名创建后不可修改。</FieldDescription>
                </Field>
                <Controller
                  control={profileForm.control}
                  name="nickname"
                  render={({ field, fieldState }) => (
                    <Field data-invalid={fieldState.invalid}>
                      <FieldLabel htmlFor="profile-nickname">昵称</FieldLabel>
                      <Input
                        id="profile-nickname"
                        placeholder="请输入昵称"
                        aria-invalid={fieldState.invalid}
                        {...field}
                      />
                      <FieldError errors={[fieldState.error]} />
                    </Field>
                  )}
                />
                <Controller
                  control={profileForm.control}
                  name="email"
                  render={({ field, fieldState }) => (
                    <Field data-invalid={fieldState.invalid}>
                      <FieldLabel htmlFor="profile-email">邮箱</FieldLabel>
                      <Input
                        id="profile-email"
                        type="email"
                        placeholder="请输入邮箱"
                        aria-invalid={fieldState.invalid}
                        {...field}
                      />
                      <FieldError errors={[fieldState.error]} />
                    </Field>
                  )}
                />
                <Field>
                  <FieldTitle>角色</FieldTitle>
                  <div className="flex flex-wrap gap-2">
                    {profile?.roles?.length ? (
                      profile.roles.map((role) => (
                        <Badge key={role.id} variant="secondary">
                          {role.name}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-sm text-muted-foreground">
                        暂无角色
                      </span>
                    )}
                  </div>
                </Field>
                <Field data-disabled>
                  <FieldLabel htmlFor="profile-created-at">注册时间</FieldLabel>
                  <Input
                    id="profile-created-at"
                    value={
                      profile?.created_at
                        ? dayjs(profile.created_at).format(
                            "YYYY-MM-DD HH:mm:ss"
                          )
                        : ""
                    }
                    disabled
                  />
                </Field>
                <Button type="submit" className="w-fit">
                  保存修改
                </Button>
              </FieldGroup>
            </form>
          </CardContent>
        </Card>

        {/* 修改密码 */}
        <Card>
          <CardHeader>
            <CardTitle>修改密码</CardTitle>
            <CardDescription>定期修改密码以提高安全性</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={passwordForm.handleSubmit(handlePasswordSubmit)}>
              <FieldGroup>
                <Controller
                  control={passwordForm.control}
                  name="old_password"
                  render={({ field, fieldState }) => (
                    <Field data-invalid={fieldState.invalid}>
                      <FieldLabel htmlFor="old-password">旧密码</FieldLabel>
                      <Input
                        id="old-password"
                        type="password"
                        autoComplete="current-password"
                        placeholder="请输入旧密码"
                        aria-invalid={fieldState.invalid}
                        {...field}
                      />
                      <FieldError errors={[fieldState.error]} />
                    </Field>
                  )}
                />
                <Controller
                  control={passwordForm.control}
                  name="new_password"
                  render={({ field, fieldState }) => (
                    <Field data-invalid={fieldState.invalid}>
                      <FieldLabel htmlFor="new-password">新密码</FieldLabel>
                      <Input
                        id="new-password"
                        type="password"
                        autoComplete="new-password"
                        placeholder="至少 8 个字符"
                        aria-invalid={fieldState.invalid}
                        {...field}
                        onChange={(event) => {
                          field.onChange(event)
                          setNewPassword(event.target.value)
                        }}
                      />
                      {newPassword && (
                        <div className="flex flex-col gap-1">
                          <Progress value={passwordStrength} />
                          <FieldDescription>
                            密码强度：
                            {passwordStrength < 50
                              ? "弱"
                              : passwordStrength < 75
                                ? "中"
                                : "强"}
                          </FieldDescription>
                        </div>
                      )}
                      <FieldError errors={[fieldState.error]} />
                    </Field>
                  )}
                />
                <Controller
                  control={passwordForm.control}
                  name="confirm_password"
                  render={({ field, fieldState }) => (
                    <Field data-invalid={fieldState.invalid}>
                      <FieldLabel htmlFor="confirm-password">
                        确认新密码
                      </FieldLabel>
                      <Input
                        id="confirm-password"
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
                <Button type="submit" className="w-fit">
                  确认修改
                </Button>
              </FieldGroup>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
