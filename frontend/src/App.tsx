import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { AuthProvider } from "@/contexts/AuthContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import {
  AdminRoute,
  GuestRoute,
  UserRoute,
} from "@/components/common/ProtectedRoute";
import { AdminLayout } from "@/components/layout/AdminLayout";
import { UserLayout } from "@/components/layout/UserLayout";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { LandingPage } from "@/pages/Landing/LandingPage";
import { LoginPage } from "@/pages/Auth/LoginPage";
import { AdminLoginPage } from "@/pages/Auth/AdminLoginPage";
import { RegisterPage } from "@/pages/Auth/RegisterPage";
import { ForgotPasswordPage } from "@/pages/Auth/ForgotPasswordPage";
import { DashboardPage } from "@/pages/Dashboard/DashboardPage";
import { DocumentsPage } from "@/pages/Documents/DocumentsPage";
import { ChatPage } from "@/pages/Chat/ChatPage";
import { MeetingsPage } from "@/pages/Meetings/MeetingsPage";
import { OCRPage } from "@/pages/OCR/OCRPage";
import { VisionPage } from "@/pages/Vision/VisionPage";
import { AgentsPage } from "@/pages/Agents/AgentsPage";
import { AnalyticsPage } from "@/pages/Analytics/AnalyticsPage";
import { SettingsPage } from "@/pages/Settings/SettingsPage";
import { AdminPage } from "@/pages/Admin/AdminPage";
import { ProfilePage } from "@/pages/Profile/ProfilePage";
import { NotFoundPage } from "@/pages/NotFound/NotFoundPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <BrowserRouter
            future={{
              v7_startTransition: true,
              v7_relativeSplatPath: true,
            }}
          >
            <Routes>
              <Route path="/" element={<LandingPage />} />

              {/* User auth */}
              <Route element={<GuestRoute portal="user" />}>
                <Route element={<AuthLayout />}>
                  <Route path="/login" element={<LoginPage />} />
                  <Route path="/register" element={<RegisterPage />} />
                  <Route path="/forgot-password" element={<ForgotPasswordPage />} />
                </Route>
              </Route>

              {/* Admin auth */}
              <Route element={<GuestRoute portal="admin" />}>
                <Route element={<AuthLayout />}>
                  <Route path="/admin/login" element={<AdminLoginPage />} />
                </Route>
              </Route>

              {/* User Portal — ChatGPT-style */}
              <Route element={<UserRoute />}>
                <Route element={<UserLayout />}>
                  <Route path="/chat" element={<ChatPage />} />
                  <Route path="/profile" element={<ProfilePage />} />
                  <Route path="/home" element={<Navigate to="/chat" replace />} />
                </Route>
              </Route>

              {/* Admin Portal — Enterprise management */}
              <Route element={<AdminRoute />}>
                <Route element={<AdminLayout />}>
                  <Route path="/admin" element={<DashboardPage />} />
                  <Route path="/admin/users" element={<AdminPage />} />
                  <Route path="/admin/organizations" element={<AdminPage />} />
                  <Route path="/admin/teams" element={<AdminPage />} />
                  <Route path="/admin/documents" element={<DocumentsPage />} />
                  <Route path="/admin/folders" element={<DocumentsPage />} />
                  <Route path="/admin/ocr" element={<OCRPage />} />
                  <Route path="/admin/vision" element={<VisionPage />} />
                  <Route path="/admin/meetings" element={<MeetingsPage />} />
                  <Route path="/admin/agents" element={<AgentsPage />} />
                  <Route path="/admin/analytics" element={<AnalyticsPage />} />
                  <Route path="/admin/api-keys" element={<AdminPage />} />
                  <Route path="/admin/storage" element={<AdminPage />} />
                  <Route path="/admin/audit" element={<AdminPage />} />
                  <Route path="/admin/subscription" element={<AdminPage />} />
                  <Route path="/admin/settings" element={<SettingsPage />} />
                  <Route path="/admin/profile" element={<ProfilePage />} />
                </Route>
              </Route>

              {/* Legacy redirects */}
              <Route path="/dashboard" element={<Navigate to="/admin" replace />} />
              <Route path="/documents" element={<Navigate to="/admin/documents" replace />} />
              <Route path="/analytics" element={<Navigate to="/admin/analytics" replace />} />
              <Route path="/settings" element={<Navigate to="/admin/settings" replace />} />
              <Route path="/meetings" element={<Navigate to="/admin/meetings" replace />} />
              <Route path="/ocr" element={<Navigate to="/admin/ocr" replace />} />
              <Route path="/vision" element={<Navigate to="/admin/vision" replace />} />
              <Route path="/agents" element={<Navigate to="/admin/agents" replace />} />

              <Route path="/404" element={<NotFoundPage />} />
              <Route path="*" element={<Navigate to="/404" replace />} />
            </Routes>
          </BrowserRouter>
          <Toaster richColors position="top-right" closeButton />
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
