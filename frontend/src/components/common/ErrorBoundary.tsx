/** 错误边界组件

 * 捕获子组件渲染错误，显示友好的错误提示。
 */

import { Component, type ErrorInfo, type ReactNode } from "react"

import { Cancel01Icon } from "@/lib/icons"
import { Button } from "@/components/ui/button"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"

interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("ErrorBoundary caught an error:", error, errorInfo)
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null })
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="flex h-svh items-center justify-center p-6">
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Cancel01Icon />
              </EmptyMedia>
              <EmptyTitle>页面出错了</EmptyTitle>
              <EmptyDescription>
                {this.state.error?.message || "发生了一个未知错误"}
              </EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <Button onClick={this.handleReset}>重试</Button>
            </EmptyContent>
          </Empty>
        </div>
      )
    }

    return this.props.children
  }
}
