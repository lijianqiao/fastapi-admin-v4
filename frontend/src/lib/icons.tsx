/**
 * Hugeicons 图标适配层
 *
 * @hugeicons/react v1.x 只导出 HugeiconsIcon 组件，
 * 图标定义在 @hugeicons/core-free-icons 中。
 * 此模块将图标定义包装为 React 组件，保持 <IconName /> 调用方式。
 */

import { HugeiconsIcon } from "@hugeicons/react"
import type { ComponentProps, FC } from "react"
import {
  Cancel01Icon as Cancel01,
  Shield02Icon as Shield02,
  Tick02Icon as Tick02,
  UnfoldMoreIcon as UnfoldMore,
  ArrowDown01Icon as ArrowDown01,
  ArrowUp01Icon as ArrowUp01,
  UserCircleIcon as UserCircle,
  Logout02Icon as Logout02,
  Menu02Icon as Menu02,
  Sun02Icon as Sun02,
  Moon02Icon as Moon02,
  ChevronLeftIcon as ChevronLeft,
  ChevronRightIcon as ChevronRight,
  ChevronsLeftIcon as ChevronsLeft,
  ChevronsRightIcon as ChevronsRight,
  DashboardCircleIcon as Dashboard02,
  UserMultipleIcon as UserMultiple,
  Key02Icon as Key02,
  FileEditIcon as FileEdit,
  UserCheck02Icon as UserCheck02,
  PlusSignIcon as PlusSign,
  PencilEdit02Icon as PencilEdit02,
  Delete02Icon as Delete02,
  MoreHorizontalIcon as MoreHorizontal,
  UserAdd02Icon as UserAssign02,
  InboxIcon as Inbox,
  ResetPasswordIcon as ResetPassword,
  PanelLeftIcon as PanelLeft,
  Settings02Icon as Settings02,
  AuditIcon as Audit,
  ViewIcon as View,
  ViewOffSlashIcon as ViewOffSlash,
} from "@hugeicons/core-free-icons"

type IconProps = Omit<ComponentProps<typeof HugeiconsIcon>, "icon">

function makeIcon(
  iconDef: NonNullable<ComponentProps<typeof HugeiconsIcon>["icon"]>
): FC<IconProps> {
  return function IconComponent({ size = 24, ...props }: IconProps) {
    return <HugeiconsIcon icon={iconDef} size={size} {...props} />
  }
}

export const Cancel01Icon = makeIcon(Cancel01)
export const Shield02Icon = makeIcon(Shield02)
export const Tick02Icon = makeIcon(Tick02)
export const UnfoldMoreIcon = makeIcon(UnfoldMore)
export const ArrowDown01Icon = makeIcon(ArrowDown01)
export const ArrowUp01Icon = makeIcon(ArrowUp01)
export const UserCircleIcon = makeIcon(UserCircle)
export const Logout02Icon = makeIcon(Logout02)
export const Menu02Icon = makeIcon(Menu02)
export const Sun02Icon = makeIcon(Sun02)
export const Moon02Icon = makeIcon(Moon02)
export const ChevronLeftIcon = makeIcon(ChevronLeft)
export const ChevronRightIcon = makeIcon(ChevronRight)
export const ChevronsLeftIcon = makeIcon(ChevronsLeft)
export const ChevronsRightIcon = makeIcon(ChevronsRight)
export const Dashboard02Icon = makeIcon(Dashboard02)
export const UserMultipleIcon = makeIcon(UserMultiple)
export const Key02Icon = makeIcon(Key02)
export const FileEditIcon = makeIcon(FileEdit)
export const UserCheck02Icon = makeIcon(UserCheck02)
export const PlusSignIcon = makeIcon(PlusSign)
export const PencilEdit02Icon = makeIcon(PencilEdit02)
export const Delete02Icon = makeIcon(Delete02)
export const MoreHorizontalIcon = makeIcon(MoreHorizontal)
export const UserAssign02Icon = makeIcon(UserAssign02)
export const InboxIcon = makeIcon(Inbox)
export const ResetPasswordIcon = makeIcon(ResetPassword)
export const PanelLeftIcon = makeIcon(PanelLeft)
export const Settings02Icon = makeIcon(Settings02)
export const AuditIcon = makeIcon(Audit)
export const ViewIcon = makeIcon(View)
export const ViewOffSlashIcon = makeIcon(ViewOffSlash)
