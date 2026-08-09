/** 角色权限分配对话框

 * 显示所有权限，按模块分组，通过 Checkbox 多选分配给角色。
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
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import api from "@/lib/api"
import type { Permission } from "@/types/permission"
import type { RoleWithPermissions } from "@/types/role"

interface AssignPermissionsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  role: RoleWithPermissions | null
  onConfirm: (permissionIds: number[]) => Promise<void>
}

export function AssignPermissionsDialog({
  open,
  onOpenChange,
  role,
  onConfirm,
}: AssignPermissionsDialogProps) {
  const [groupedPerms, setGroupedPerms] = useState<Record<string, Permission[]>>({})
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (open) {
      setIsLoading(true)
      api
        .get("/permissions", { params: { grouped: true, page_size: 200 } })
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
        : [...prev, permId],
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
    await onConfirm(selectedIds)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>分配权限</DialogTitle>
          <DialogDescription>
            为角色「{role?.name}」分配权限
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : (
          <ScrollArea className="max-h-80">
            <div className="space-y-4 pr-4">
              {Object.entries(groupedPerms).map(([moduleName, perms]) => {
                const moduleIds = perms.map((p) => p.id)
                const allSelected = moduleIds.every((id) =>
                  selectedIds.includes(id),
                )
                const someSelected = moduleIds.some((id) =>
                  selectedIds.includes(id),
                )

                return (
                  <div key={moduleName}>
                    <div className="flex items-center gap-3 pb-2">
                      <Checkbox
                        id={`module-${moduleName}`}
                        checked={allSelected ? true : someSelected ? "indeterminate" : false}
                        onCheckedChange={() => handleToggleModule(perms)}
                      />
                      <Label
                        htmlFor={`module-${moduleName}`}
                        className="cursor-pointer font-medium"
                      >
                        {moduleName}（{perms.length}）
                      </Label>
                    </div>
                    <Separator className="mb-2" />
                    <div className="ml-6 space-y-2">
                      {perms.map((perm) => (
                        <div key={perm.id} className="flex items-center gap-3">
                          <Checkbox
                            id={`perm-${perm.id}`}
                            checked={selectedIds.includes(perm.id)}
                            onCheckedChange={() => handleToggle(perm.id)}
                          />
                          <Label
                            htmlFor={`perm-${perm.id}`}
                            className="flex-1 cursor-pointer"
                          >
                            <span className="font-mono text-sm">{perm.code}</span>
                            <span className="ml-2 text-sm text-muted-foreground">
                              {perm.name}
                            </span>
                          </Label>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          </ScrollArea>
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
