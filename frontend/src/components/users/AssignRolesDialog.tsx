/** 用户角色分配对话框

 * 显示所有可用角色，通过 Checkbox 多选分配给用户。
 */

import { useEffect, useState } from "react"

import { Shield02Icon } from "@/lib/icons"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import api from "@/lib/api"
import type { Role } from "@/types/role"
import type { UserWithRoles } from "@/types/user"

/** 角色数量通常不多，但仍按后端上限循环翻页，避免超过单页上限时静默丢数据 */
async function fetchAllRoles(): Promise<Role[]> {
  const pageSize = 100
  const roles: Role[] = []
  for (let page = 1; ; page += 1) {
    const res = await api.get("/roles", { params: { page, page_size: pageSize } })
    const items: Role[] = res.data?.data?.items ?? []
    const total: number = res.data?.data?.total ?? 0
    roles.push(...items)
    if (items.length === 0 || roles.length >= total) break
  }
  return roles
}

interface AssignRolesDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  user: UserWithRoles | null
  onConfirm: (roleIds: number[]) => Promise<boolean>
}

export function AssignRolesDialog({
  open,
  onOpenChange,
  user,
  onConfirm,
}: AssignRolesDialogProps) {
  const [roles, setRoles] = useState<Role[]>([])
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    if (open) {
      setIsLoading(true)
      fetchAllRoles()
        .then(setRoles)
        .finally(() => setIsLoading(false))

      if (user) {
        setSelectedIds(user.roles?.map((r) => r.id) ?? [])
      }
    }
  }, [open, user])

  const handleToggle = (roleId: number) => {
    setSelectedIds((prev) =>
      prev.includes(roleId)
        ? prev.filter((id) => id !== roleId)
        : [...prev, roleId]
    )
  }

  const handleConfirm = async () => {
    setIsSubmitting(true)
    try {
      const ok = await onConfirm(selectedIds)
      if (ok) onOpenChange(false)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>分配角色</DialogTitle>
          <DialogDescription>
            为用户「{user?.username}」分配角色
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex flex-col gap-3">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-8 w-full" />
            ))}
          </div>
        ) : roles.length === 0 ? (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Shield02Icon />
              </EmptyMedia>
              <EmptyTitle>暂无可用角色</EmptyTitle>
              <EmptyDescription>请先在角色管理中创建角色。</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <ScrollArea className="max-h-60">
            <FieldSet>
              <FieldLegend variant="label">可分配角色</FieldLegend>
              <FieldDescription>
                勾选后将替换该用户的全部角色。
              </FieldDescription>
              <FieldGroup className="gap-3">
                {roles.map((role) => (
                  <Field key={role.id} orientation="horizontal">
                    <Checkbox
                      id={`role-${role.id}`}
                      checked={selectedIds.includes(role.id)}
                      onCheckedChange={() => handleToggle(role.id)}
                    />
                    <FieldLabel htmlFor={`role-${role.id}`}>
                      <span className="font-medium">{role.name}</span>
                      {role.description && (
                        <span className="text-sm text-muted-foreground">
                          {role.description}
                        </span>
                      )}
                    </FieldLabel>
                  </Field>
                ))}
              </FieldGroup>
            </FieldSet>
          </ScrollArea>
        )}

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isSubmitting}
          >
            取消
          </Button>
          <Button type="button" onClick={handleConfirm} disabled={isSubmitting}>
            {isSubmitting && <Spinner data-icon="inline-start" />}
            确定分配
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
