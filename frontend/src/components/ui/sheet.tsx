"use client"

import * as React from "react"
import { Dialog as DialogPrimitive } from "@base-ui/react/dialog"
import { Cancel01Icon } from "@/lib/icons"

import { cn } from "@/lib/utils"

function Sheet({ ...props }: DialogPrimitive.Root.Props) {
  return <DialogPrimitive.Root data-slot="sheet" {...props} />
}

function SheetTrigger({ ...props }: DialogPrimitive.Trigger.Props) {
  return <DialogPrimitive.Trigger data-slot="sheet-trigger" {...props} />
}

function SheetClose({ ...props }: DialogPrimitive.Close.Props) {
  return <DialogPrimitive.Close data-slot="sheet-close" {...props} />
}

function SheetContent({
  className,
  children,
  side = "right",
  ...props
}: DialogPrimitive.Popup.Props & {
  side?: "left" | "right" | "top" | "bottom"
}) {
  const sideClasses: Record<string, string> = {
    right:
      "inset-y-0 right-0 h-full w-3/4 border-l sm:max-w-sm data-open:slide-in-from-right data-closed:slide-out-to-right",
    left: "inset-y-0 left-0 h-full w-3/4 border-r sm:max-w-sm data-open:slide-in-from-left data-closed:slide-out-to-left",
    top: "inset-x-0 top-0 border-b data-open:slide-in-from-top data-closed:slide-out-to-top",
    bottom:
      "inset-x-0 bottom-0 border-t data-open:slide-in-from-bottom data-closed:slide-out-to-bottom",
  }

  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Backdrop
        data-slot="sheet-overlay"
        className="fixed inset-0 isolate z-50 bg-black/30 duration-100 supports-backdrop-filter:backdrop-blur-sm data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0"
      />
      <DialogPrimitive.Popup
        data-slot="sheet-content"
        className={cn(
          "fixed z-50 flex flex-col gap-4 bg-background p-6 shadow-lg duration-100 outline-none data-open:animate-in data-closed:animate-out",
          sideClasses[side],
          className
        )}
        {...props}
      >
        {children}
        <DialogPrimitive.Close
          data-slot="sheet-close"
          className="absolute top-4 right-4 rounded-lg p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <Cancel01Icon className="size-4" />
          <span className="sr-only">Close</span>
        </DialogPrimitive.Close>
      </DialogPrimitive.Popup>
    </DialogPrimitive.Portal>
  )
}

function SheetHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-header"
      className={cn("flex flex-col gap-1.5", className)}
      {...props}
    />
  )
}

function SheetTitle({ className, ...props }: DialogPrimitive.Title.Props) {
  return (
    <DialogPrimitive.Title
      data-slot="sheet-title"
      className={cn("text-base leading-none font-medium", className)}
      {...props}
    />
  )
}

function SheetDescription({
  className,
  ...props
}: DialogPrimitive.Description.Props) {
  return (
    <DialogPrimitive.Description
      data-slot="sheet-description"
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  )
}

export {
  Sheet,
  SheetTrigger,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
}
