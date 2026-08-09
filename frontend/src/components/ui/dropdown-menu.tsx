"use client"

import * as React from "react"
import { Menu as DropdownMenuPrimitive } from "@base-ui/react/menu"

import { cn } from "@/lib/utils"

function DropdownMenu({ ...props }: DropdownMenuPrimitive.Root.Props) {
  return <DropdownMenuPrimitive.Root data-slot="dropdown-menu" {...props} />
}

function DropdownMenuTrigger({ ...props }: DropdownMenuPrimitive.Trigger.Props) {
  return <DropdownMenuPrimitive.Trigger data-slot="dropdown-menu-trigger" {...props} />
}

function DropdownMenuContent({
  className,
  side = "bottom",
  align = "center",
  sideOffset = 4,
  ...props
}: DropdownMenuPrimitive.Popup.Props &
  Pick<DropdownMenuPrimitive.Positioner.Props, "align" | "side" | "sideOffset">) {
  return (
    <DropdownMenuPrimitive.Portal>
      <DropdownMenuPrimitive.Positioner side={side} align={align} sideOffset={sideOffset} className="z-50">
        <DropdownMenuPrimitive.Popup
          data-slot="dropdown-menu-content"
          className={cn(
            "cn-menu-target cn-menu-translucent z-50 min-w-36 overflow-hidden rounded-3xl bg-popover p-1.5 text-popover-foreground shadow-lg ring-1 ring-foreground/5 dark:ring-foreground/10 data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
            className
          )}
          {...props}
        />
      </DropdownMenuPrimitive.Positioner>
    </DropdownMenuPrimitive.Portal>
  )
}

function DropdownMenuItem({ className, ...props }: DropdownMenuPrimitive.Item.Props) {
  return (
    <DropdownMenuPrimitive.Item
      data-slot="dropdown-menu-item"
      className={cn(
        "relative flex w-full cursor-default items-center gap-2.5 rounded-2xl py-2 pr-8 pl-3 text-sm font-medium outline-hidden select-none focus:bg-accent focus:text-accent-foreground data-disabled:pointer-events-none data-disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        className
      )}
      {...props}
    />
  )
}

function DropdownMenuSeparator({ className, ...props }: DropdownMenuPrimitive.Separator.Props) {
  return (
    <DropdownMenuPrimitive.Separator
      data-slot="dropdown-menu-separator"
      className={cn("pointer-events-none -mx-1.5 my-1.5 h-px bg-border", className)}
      {...props}
    />
  )
}

function DropdownMenuLabel({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="dropdown-menu-label"
      className={cn("px-3 py-2 text-xs text-muted-foreground", className)}
      {...props}
    />
  )
}

export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuLabel,
}
