"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

function ScrollArea({ className, children, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="scroll-area"
      className={cn("relative overflow-auto", className)}
      {...props}
    >
      {children}
    </div>
  )
}

function ScrollBar({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="scroll-bar"
      className={cn("flex touch-none select-none transition-colors", className)}
      {...props}
    />
  )
}

export { ScrollArea, ScrollBar }
