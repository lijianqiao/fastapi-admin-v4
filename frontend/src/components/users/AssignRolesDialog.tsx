/** 用户角色分配对话框

 * 显示所有可用角色，通过 Checkbox 多选分配给用户。
 */

import { useEffect, useState } from "react"

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
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import api from "@/lib/api"
import type { Role } from "@/types/role"
import type { UserWithRoles } from "@/types/user"

interface AssignRolesDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  user: UserWithRoles | null
  onConfirm: (roleIds: number[]) => Promise<void>
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

  useEffect(() => {
    if (open) {
      setIsLoading(true)
      api
        .get("/roles", { params: { page_size: 100 } })
        .then((res) => {
          setRoles(res.data?.data?.items ?? [])
        })
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
        : [...prev, roleId],
    )
  }

  const handleConfirm = async () => {
    await onConfirm(selectedIds)
    onOpenChange(false)
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
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : (
          <div className="max-h-60 space-y-3 overflow-y-auto">
            {roles.length === 0 ? (
              <p className="py-4 text-center text-sm text-muted-foreground">
                暂无可用角色
              </p>
            ) : (
              roles.map((role) => (
                <div key={role.id} className="flex items-center gap-3">
                  <Checkbox
                    id={`role-${role.id}`}
                    checked={selectedIds.includes(role.id)}
                    onCheckedChange={() => handleToggle(role.id)}
                  />
                  <Label
                    htmlFor={`role-${role.id}`}
                    className="flex-1 cursor-pointer"
                  >
                    <span className="font-medium">{role.name}</span>
                    {role.description && (
                      <span className="ml-2 text-sm text-muted-foreground">
                        {role.description}
                      </span>
                    )}
                  </Label>
                </div>
              ))
            )}
          </div>
        )}

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            取消
          </Button>
          <Button type="button" onClick={handleConfirm}>
            确定分配
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
