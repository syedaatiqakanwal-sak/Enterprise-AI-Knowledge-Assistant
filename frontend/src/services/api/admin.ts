import { api } from "./client";
import type { ApiResponse } from "@/types";

export interface AdminOrganization {
  id: string;
  tenant_id: string;
  name: string;
  logo_url?: string | null;
  brand_primary?: string | null;
  brand_secondary?: string | null;
  domain?: string | null;
  timezone: string;
  language: string;
  region: string;
  ai_settings?: Record<string, unknown>;
  storage_settings?: Record<string, unknown>;
  status: string;
  created_at?: string | null;
}

export interface AdminTeam {
  id: string;
  tenant_id: string;
  organization_id: string;
  name: string;
  description?: string | null;
  manager_id?: string | null;
  created_at?: string | null;
}

export interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  status: string;
  is_active: boolean;
  is_verified: boolean;
  tenant_id?: string | null;
  organization_id?: string | null;
  team_id?: string | null;
  roles: string[];
  last_login?: string | null;
  created_at?: string | null;
}

export interface AuditLogItem {
  id: string;
  action: string;
  actor_id?: string | null;
  resource_type?: string | null;
  resource_id?: string | null;
  details?: Record<string, unknown>;
  success: boolean;
  created_at?: string | null;
}

export interface ApiKeyItem {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  is_active: boolean;
  usage_count: number;
  last_used_at?: string | null;
  created_at?: string | null;
  api_key?: string;
}

export interface StorageDashboard {
  tenant_id: string;
  quota_bytes: number;
  used_bytes: number;
  breakdown: Record<string, number>;
  counts: Record<string, number>;
  usage_limits: Record<string, number>;
  subscription: {
    plan: string;
    status: string;
    seats: number;
    renews_at?: string | null;
  };
}

export const adminApi = {
  organizations: {
    list: () => api.get<ApiResponse<AdminOrganization[]>>("/admin/organizations"),
    create: (body: Partial<AdminOrganization> & { name: string }) =>
      api.post<ApiResponse<AdminOrganization>>("/admin/organizations", body),
    update: (id: string, body: Partial<AdminOrganization>) =>
      api.put<ApiResponse<AdminOrganization>>(`/admin/organizations/${id}`, body),
    remove: (id: string) =>
      api.delete<ApiResponse<{ id: string }>>(`/admin/organizations/${id}`),
  },
  users: {
    list: (params?: { limit?: number; offset?: number; status?: string }) =>
      api.get<
        ApiResponse<{
          items: AdminUser[];
          total: number;
          limit: number;
          offset: number;
        }>
      >("/admin/users", { params }),
    invite: (body: {
      email: string;
      role?: string;
      organization_id?: string;
      team_id?: string;
      full_name?: string;
    }) => api.post<ApiResponse<Record<string, unknown>>>("/admin/users/invite", body),
    update: (id: string, body: Record<string, unknown>) =>
      api.put<ApiResponse<AdminUser>>(`/admin/users/${id}`, body),
    remove: (id: string) =>
      api.delete<ApiResponse<{ id: string }>>(`/admin/users/${id}`),
  },
  teams: {
    list: (organization_id?: string) =>
      api.get<ApiResponse<AdminTeam[]>>("/admin/teams", {
        params: organization_id ? { organization_id } : undefined,
      }),
    create: (body: {
      name: string;
      organization_id: string;
      description?: string;
      manager_id?: string;
    }) => api.post<ApiResponse<AdminTeam>>("/admin/teams", body),
    update: (id: string, body: Partial<AdminTeam>) =>
      api.put<ApiResponse<AdminTeam>>(`/admin/teams/${id}`, body),
    remove: (id: string) =>
      api.delete<ApiResponse<{ id: string }>>(`/admin/teams/${id}`),
    assign: (
      id: string,
      body: { user_ids: string[]; manager_id?: string },
    ) => api.post<ApiResponse<AdminTeam>>(`/admin/teams/${id}/assign`, body),
  },
  audit: (params?: { action?: string; limit?: number; offset?: number }) =>
    api.get<
      ApiResponse<{
        items: AuditLogItem[];
        total: number;
      }>
    >("/admin/audit", { params }),
  storage: () => api.get<ApiResponse<StorageDashboard>>("/admin/storage"),
  apiKeys: {
    list: () => api.get<ApiResponse<ApiKeyItem[]>>("/admin/api-keys"),
    create: (body: { name: string; scopes?: string[] }) =>
      api.post<ApiResponse<ApiKeyItem>>("/admin/api-keys", body),
    remove: (id: string) =>
      api.delete<ApiResponse<{ id: string }>>(`/admin/api-keys/${id}`),
    rotate: (id: string) =>
      api.post<ApiResponse<ApiKeyItem>>(`/admin/api-keys/${id}/rotate`),
  },
  subscription: () =>
    api.get<ApiResponse<Record<string, unknown>>>("/admin/subscription"),
};
