"use client"

import * as React from "react"
import {
  Controller,
  FormProvider,
  type ControllerProps,
  type FieldPath,
  type FieldValues,
} from "react-hook-form"

import { cn } from "@/lib/utils"
import { Label } from "@/components/ui/label"

// Slot：将 props 合并到单个子元素上
// @base-ui/react 不导出 Slot，此处自行实现等价功能
function Slot({ children, ...props }: React.PropsWithChildren<React.HTMLAttributes<HTMLElement>>) {
  if (React.isValidElement(children)) {
    return React.cloneElement(children, {
      ...props,
      ...(children.props as object),
    })
  }
  return null
}

// Form 是 FormProvider 的别名，不渲染 DOM 元素
// 实际的 <form> 元素由使用者在 Form 内部手动渲染
const Form = FormProvider

type FormFieldContextValue<
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>,
> = { name: TName }

const FormFieldContext = React.createContext<FormFieldContextValue>(
  {} as FormFieldContextValue,
)

// FormField 使用 react-hook-form 的 Controller，render prop 不会泄露到 DOM
// 泛型参数从 name 推断，保持类型精确
const FormField = <
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>,
>({
  ...props
}: ControllerProps<TFieldValues, TName>) => {
  return (
    <FormFieldContext.Provider value={{ name: props.name }}>
      <Controller {...props} />
    </FormFieldContext.Provider>
  )
}

function FormItem({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="form-item"
      className={cn("grid gap-2", className)}
      {...props}
    />
  )
}

function FormLabel({ className, ...props }: React.ComponentProps<typeof Label>) {
  return <Label data-slot="form-label" className={cn(className)} {...props} />
}

function FormControl({ ...props }: React.ComponentProps<typeof Slot>) {
  return <Slot data-slot="form-control" {...props} />
}

function FormDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      data-slot="form-description"
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  )
}

function FormMessage({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      data-slot="form-message"
      className={cn("text-sm font-medium text-destructive", className)}
      {...props}
    />
  )
}

export {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
}
