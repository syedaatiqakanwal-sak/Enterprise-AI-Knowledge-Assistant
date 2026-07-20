import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { PageLoader } from "@/components/common/Loader";

/** Authenticated users only. */
export function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) return <PageLoader />;
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <Outlet />;
}

/** Admin Portal — admin/manager only. Employees get 403 → /chat. */
export function AdminRoute() {
  const { isAuthenticated, isLoading, isAdminPortal } = useAuth();
  const location = useLocation();

  if (isLoading) return <PageLoader />;
  if (!isAuthenticated) {
    return <Navigate to="/admin/login" replace state={{ from: location }} />;
  }
  if (!isAdminPortal) {
    return <Navigate to="/chat" replace />;
  }
  return <Outlet />;
}

/** User Portal — employees. Admins are redirected to /admin. */
export function UserRoute() {
  const { isAuthenticated, isLoading, isAdminPortal } = useAuth();
  const location = useLocation();

  if (isLoading) return <PageLoader />;
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (isAdminPortal) {
    return <Navigate to="/admin" replace />;
  }
  return <Outlet />;
}

/** Guest pages — redirect authenticated users to their portal home. */
export function GuestRoute({ portal }: { portal?: "admin" | "user" }) {
  const { isAuthenticated, isLoading, isAdminPortal, homePath } = useAuth();
  if (isLoading) return <PageLoader />;
  if (isAuthenticated) {
    if (portal === "admin" && !isAdminPortal) {
      return <Navigate to="/chat" replace />;
    }
    if (portal === "user" && isAdminPortal) {
      return <Navigate to="/admin" replace />;
    }
    return <Navigate to={homePath} replace />;
  }
  return <Outlet />;
}

/** @deprecated use AdminRoute */
export function ProtectedRouteLegacy({ adminOnly = false }: { adminOnly?: boolean }) {
  if (adminOnly) return <AdminRoute />;
  return <ProtectedRoute />;
}
