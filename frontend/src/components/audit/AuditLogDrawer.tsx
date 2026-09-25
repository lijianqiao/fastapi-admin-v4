/** 审计日志详情抽屉

 * 从右侧滑出，把表格里被截断的一条记录展开成可扫读的详情。
 */

import dayjs from "dayjs"

import { Badge } from "@/components/ui/badge"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import type { AuditLog } from "@/types/audit"

export const AUDIT_ACTION_LABELS: Record<string, string> = {
  register: "注册",
  login: "登录",
  logout: "退出",
  create_user: "创建用户",
  update_user: "更新用户",
  delete_user: "删除用户",
  assign_roles: "分配角色",
  create_role: "创建角色",
  update_role: "更新角色",
  delete_role: "删除角色",
  assign_permissions: "分配权限",
  create_permission: "创建权限",
  update_permission: "更新权限",
  delete_permission: "删除权限",
  restore_user: "恢复用户",
  purge_user: "永久删除用户",
  restore_role: "恢复角色",
  purge_role: "永久删除角色",
  restore_permission: "恢复权限",
  purge_permission: "永久删除权限",
  update_profile: "更新资料",
  change_password: "修改密码",
  reset_password: "重置密码",
}

/** 把操作码转成中文；未知码原样显示 */
export function auditActionLabel(action: string): string {
  return AUDIT_ACTION_LABELS[action] ?? action
}

interface AuditLogDrawerProps {
  log: AuditLog | null
  onClose: () => void
}

interface FactProps {
  label: string
  value: string
  mono?: boolean
}

function Fact({ label, value, mono = false }: FactProps) {
  return (
    <div className="rounded-lg bg-muted/50 px-3 py-2.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd
        className={
          mono
            ? "mt-1 font-mono text-sm break-all text-foreground"
            : "mt-1 text-sm break-all text-foreground"
        }
      >
        {value}
      </dd>
    </div>
  )
}

export function AuditLogDrawer({ log, onClose }: AuditLogDrawerProps) {
  const label = log ? auditActionLabel(log.action) : ""

  return (
    <Sheet
      open={log !== null}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      <SheetContent
        side="right"
        className="w-full gap-0 overflow-hidden p-0 sm:max-w-md"
      >
        {log ? (
          <div className="flex h-full flex-col">
            <SheetHeader className="gap-3 border-b px-6 pt-6 pr-12 pb-5">
              <div className="flex items-center gap-2">
                <Badge variant="outline">{label}</Badge>
                <span className="font-mono text-xs text-muted-foreground">
                  #{log.id}
                </span>
              </div>
              <SheetTitle className="text-xl tracking-tight">
                {log.username || "未知用户"}
              </SheetTitle>
              <SheetDescription>
                {dayjs(log.created_at).format("YYYY年M月D日 HH:mm:ss")}
              </SheetDescription>
            </SheetHeader>

            <div className="flex-1 overflow-y-auto px-6 py-5">
              <dl className="grid grid-cols-2 gap-2.5">
                <Fact label="操作码" value={log.action} mono />
                <Fact label="IP 地址" value={log.ip || "未记录"} mono />
                <Fact
                  label="用户 ID"
                  value={log.user_id === null ? "未关联" : String(log.user_id)}
                  mono
                />
                <Fact label="操作对象" value={log.target || "无"} mono />
              </dl>

              <section className="mt-6">
                <h2 className="text-xs text-muted-foreground">记录说明</h2>
                <p className="mt-2 rounded-lg border bg-background px-4 py-3 text-sm leading-6 whitespace-pre-wrap break-words">
                  {log.detail || "这条记录没有附加说明。"}
                </p>
              </section>
            </div>
          </div>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}
