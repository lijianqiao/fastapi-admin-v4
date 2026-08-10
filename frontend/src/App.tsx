import { useEffect } from "react"
import { Routes, Route } from "react-router"

import { AppLayout } from "@/components/layout/AppLayout"
import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { ErrorBoundary } from "@/components/common/ErrorBoundary"
import { Spinner } from "@/components/ui/spinner"
import { useAuth } from "@/hooks/use-auth"
import { PERMISSIONS, ROUTES } from "@/lib/constants"
import { AuditLogsPage } from "@/pages/AuditLogsPage"
import { DashboardPage } from "@/pages/DashboardPage"
import { ForbiddenPage } from "@/pages/ForbiddenPage"
import { LoginPage } from "@/pages/LoginPage"
import { NotFoundPage } from "@/pages/NotFoundPage"
import { PermissionsPage } from "@/pages/PermissionsPage"
import { PermissionsTrashPage } from "@/pages/PermissionsTrashPage"
import { ProfilePage } from "@/pages/ProfilePage"
import { RolesPage } from "@/pages/RolesPage"
import { RolesTrashPage } from "@/pages/RolesTrashPage"
import { UsersPage } from "@/pages/UsersPage"
import { UsersTrashPage } from "@/pages/UsersTrashPage"

export function App() {
  const { bootstrap, isInitialized } = useAuth()

  // 应用启动时用 refresh_token cookie 尝试恢复会话，避免刷新页面被误判为未登录
  useEffect(() => {
    bootstrap()
  }, [bootstrap])

  if (!isInitialized) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner className="size-6 text-muted-foreground" />
      </div>
    )
  }

  return (
    <ErrorBoundary>
      <Routes>
        {/* 登录页 */}
        <Route path={ROUTES.LOGIN} element={<LoginPage />} />

        {/* 受保护路由 */}
        <Route
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route path={ROUTES.DASHBOARD} element={<DashboardPage />} />
          <Route
            path={ROUTES.USERS}
            element={
              <ProtectedRoute permission={PERMISSIONS.USER_READ}>
                <UsersPage />
              </ProtectedRoute>
            }
          />
          <Route
            path={ROUTES.USERS_TRASH}
            element={
              <ProtectedRoute permission={PERMISSIONS.USER_DELETE}>
                <UsersTrashPage />
              </ProtectedRoute>
            }
          />
          <Route
            path={ROUTES.ROLES}
            element={
              <ProtectedRoute permission={PERMISSIONS.ROLE_READ}>
                <RolesPage />
              </ProtectedRoute>
            }
          />
          <Route
            path={ROUTES.ROLES_TRASH}
            element={
              <ProtectedRoute permission={PERMISSIONS.ROLE_DELETE}>
                <RolesTrashPage />
              </ProtectedRoute>
            }
          />
          <Route
            path={ROUTES.PERMISSIONS}
            element={
              <ProtectedRoute permission={PERMISSIONS.PERMISSION_READ}>
                <PermissionsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path={ROUTES.PERMISSIONS_TRASH}
            element={
              <ProtectedRoute permission={PERMISSIONS.PERMISSION_DELETE}>
                <PermissionsTrashPage />
              </ProtectedRoute>
            }
          />
          <Route path={ROUTES.PROFILE} element={<ProfilePage />} />
          <Route
            path={ROUTES.AUDIT}
            element={
              <ProtectedRoute permission={PERMISSIONS.AUDIT_READ}>
                <AuditLogsPage />
              </ProtectedRoute>
            }
          />
        </Route>

        {/* 错误页面 */}
        <Route path={ROUTES.FORBIDDEN} element={<ForbiddenPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </ErrorBoundary>
  )
}

export default App
