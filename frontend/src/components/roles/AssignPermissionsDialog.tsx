/** 角色权限分配对话框

 * 显示所有权限，按模块分组，通过 Checkbox 多选分配给角色。
 */

import { useEffect, useState } from "react"

import { Key02Icon } from "@/lib/icons"
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
import { Field, FieldGroup, FieldLabel, FieldSet } from "@/components/ui/field"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import api from "@/lib/api"
import type { Permission } from "@/types/permission"
import type { RoleWithPermissions } from "@/types/role"

interface AssignPermissionsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  role: RoleWithPermissions | null
  onConfirm: (permissionIds: number[]) => Promise<boolean>
}

export function AssignPermissionsDialog({
  open,
  onOpenChange,
  role,
  onConfirm,
}: AssignPermissionsDialogProps) {
  const [groupedPerms, setGroupedPerms] = useState<
    Record<string, Permission[]>
  >({})
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    if (open) {
      setIsLoading(true)
      api
        .get("/permissions", { params: { grouped: true } })
        .then((res) => {
          setGroupedPerms(res.data?.data ?? {})
        })
        .finally(() => setIsLoading(false))

      if (role) {
        setSelectedIds(role.permissions?.map((p) => p.id) ?? [])
      }
    }
  }, [open, role])

  const handleToggle = (permId: number) => {
    setSelectedIds((prev) =>
      prev.includes(permId)
        ? prev.filter((id) => id !== permId)
        : [...prev, permId]
    )
  }

  const handleToggleModule = (modulePerms: Permission[]) => {
    const moduleIds = modulePerms.map((p) => p.id)
    const allSelected = moduleIds.every((id) => selectedIds.includes(id))
    if (allSelected) {
      setSelectedIds((prev) => prev.filter((id) => !moduleIds.includes(id)))
    } else {
      setSelectedIds((prev) => [...new Set([...prev, ...moduleIds])])
    }
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
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>分配权限</DialogTitle>
          <DialogDescription>为角色「{role?.name}」分配权限</DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex flex-col gap-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-8 w-full" />
            ))}
          </div>
        ) : Object.keys(groupedPerms).length === 0 ? (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Key02Icon />
              </EmptyMedia>
              <EmptyTitle>暂无可分配权限</EmptyTitle>
              <EmptyDescription>
                请先在权限管理中创建权限定义。
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <ScrollArea className="max-h-80">
            <FieldGroup className="pr-4">
              {Object.entries(groupedPerms).map(([moduleName, perms]) => {
                const moduleIds = perms.map((perm) => perm.id)
                const allSelected = moduleIds.every((id) =>
                  selectedIds.includes(id)
                )
                const someSelected = moduleIds.some((id) =>
                  selectedIds.includes(id)
                )

                return (
                  <FieldSet key={moduleName}>
                    <Field orientation="horizontal">
                      <Checkbox
                        id={`module-${moduleName}`}
                        checked={allSelected}
                        indeterminate={!allSelected && someSelected}
                        onCheckedChange={() => handleToggleModule(perms)}
                      />
                      <FieldLabel htmlFor={`module-${moduleName}`}>
                        {moduleName}（{perms.length}）
                      </FieldLabel>
                    </Field>
                    <Separator />
                    <FieldGroup className="ml-6 gap-3">
                      {perms.map((perm) => (
                        <Field key={perm.id} orientation="horizontal">
                          <Checkbox
                            id={`perm-${perm.id}`}
                            checked={selectedIds.includes(perm.id)}
                            onCheckedChange={() => handleToggle(perm.id)}
                          />
                          <FieldLabel
                            htmlFor={`perm-${perm.id}`}
                            className="font-normal"
                          >
                            <span className="font-mono text-sm">
                              {perm.code}
                            </span>
                            <span className="text-sm text-muted-foreground">
                              {perm.name}
                            </span>
                          </FieldLabel>
                        </Field>
                      ))}
                    </FieldGroup>
                  </FieldSet>
                )
              })}
            </FieldGroup>
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
