/** 个人中心页

 * 个人信息编辑 + 修改密码。
 */

import { useEffect, useState } from "react"
import { useForm } from "react-hook-form"
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
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { PageHeader } from "@/components/layout/PageHeader"
import api from "@/lib/api"
import { useAuthStore } from "@/store/auth"
import type { UserWithRoles } from "@/types/user"

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
  const [profile, setProfile] = useState<UserWithRoles | null>(user as UserWithRoles | null)

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
        const data: UserWithRoles = response.data?.data
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
            <Form {...profileForm}>
              <form
                onSubmit={profileForm.handleSubmit(handleProfileSubmit)}
                className="space-y-4"
              >
                <FormItem>
                  <FormLabel>用户名</FormLabel>
                  <Input value={profile?.username ?? ""} disabled />
                </FormItem>
                <FormField
                  control={profileForm.control}
                  name="nickname"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>昵称</FormLabel>
                      <FormControl>
                        <Input placeholder="请输入昵称" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={profileForm.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>邮箱</FormLabel>
                      <FormControl>
                        <Input type="email" placeholder="请输入邮箱" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormItem>
                  <FormLabel>角色</FormLabel>
                  <div className="flex flex-wrap gap-2">
                    {profile?.roles?.map((role) => (
                      <Badge key={role.id} variant="secondary">
                        {role.name}
                      </Badge>
                    )) ?? <span className="text-muted-foreground">暂无角色</span>}
                  </div>
                </FormItem>
                <FormItem>
                  <FormLabel>注册时间</FormLabel>
                  <Input
                    value={
                      profile?.created_at
                        ? dayjs(profile.created_at).format("YYYY-MM-DD HH:mm:ss")
                        : ""
                    }
                    disabled
                  />
                </FormItem>
                <Button type="submit">保存修改</Button>
              </form>
            </Form>
          </CardContent>
        </Card>

        {/* 修改密码 */}
        <Card>
          <CardHeader>
            <CardTitle>修改密码</CardTitle>
            <CardDescription>定期修改密码以提高安全性</CardDescription>
          </CardHeader>
          <CardContent>
            <Form {...passwordForm}>
              <form
                onSubmit={passwordForm.handleSubmit(handlePasswordSubmit)}
                className="space-y-4"
              >
                <FormField
                  control={passwordForm.control}
                  name="old_password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>旧密码</FormLabel>
                      <FormControl>
                        <Input type="password" placeholder="请输入旧密码" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={passwordForm.control}
                  name="new_password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>新密码</FormLabel>
                      <FormControl>
                        <Input
                          type="password"
                          placeholder="至少 8 个字符"
                          {...field}
                          onChange={(e) => {
                            field.onChange(e)
                            setNewPassword(e.target.value)
                          }}
                        />
                      </FormControl>
                      <FormMessage />
                      {newPassword && (
                        <div className="space-y-1">
                          <Progress value={passwordStrength} className="h-2" />
                          <p className="text-xs text-muted-foreground">
                            密码强度：{passwordStrength < 50 ? "弱" : passwordStrength < 75 ? "中" : "强"}
                          </p>
                        </div>
                      )}
                    </FormItem>
                  )}
                />
                <FormField
                  control={passwordForm.control}
                  name="confirm_password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>确认新密码</FormLabel>
                      <FormControl>
                        <Input type="password" placeholder="请再次输入新密码" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button type="submit">确认修改</Button>
              </form>
            </Form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
