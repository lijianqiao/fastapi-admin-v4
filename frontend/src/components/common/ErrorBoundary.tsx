/** 错误边界组件

 * 捕获子组件渲染错误，显示友好的错误提示。
 */

import { Component, type ErrorInfo, type ReactNode } from "react"

import { Button } from "@/components/ui/button"

interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
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
        <div className="flex h-svh flex-col items-center justify-center gap-4 p-6">
          <div className="text-center">
            <h1 className="text-2xl font-bold">页面出错了</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              {this.state.error?.message || "发生了一个未知错误"}
            </p>
          </div>
          <Button onClick={this.handleReset}>重试</Button>
        </div>
      )
    }

    return this.props.children
  }
}
