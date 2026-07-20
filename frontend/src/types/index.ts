/** Shared TypeScript contracts matching backend Module 3–5 envelopes. */

export interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T | null;
  errors: Record<string, unknown> | null;
}

export interface Role {
  id: string;
  name: string;
  description?: string | null;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone?: string | null;
  is_active: boolean;
  is_verified: boolean;
  last_login?: string | null;
  created_at: string;
  updated_at?: string | null;
  roles: Role[];
  role?: string | null;
  permissions?: string[];
  tenant_id?: string | null;
  organization_id?: string | null;
  team_id?: string | null;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthData {
  user: User;
  tokens: TokenPair;
}

export interface UserListData {
  items: User[];
  total: number;
  limit: number;
  offset: number;
}

export type ThemeMode = "light" | "dark" | "system";

export type DocumentStatus =
  | "uploading"
  | "processing"
  | "ready"
  | "archived"
  | "deleted"
  | "failed";

export type DocumentVisibility = "private" | "company" | "public" | "admin_only";

export interface DocumentVersion {
  id: string;
  version: number;
  size: number;
  checksum?: string | null;
  mime_type: string;
  created_at: string;
}

export interface DocumentItem {
  id: string;
  uuid: string;
  owner_id: string;
  owner_name?: string | null;
  company_id?: string | null;
  folder_id?: string | null;
  filename: string;
  original_filename: string;
  extension: string;
  mime_type: string;
  size: number;
  storage_path: string;
  thumbnail_path?: string | null;
  status: DocumentStatus | string;
  visibility: DocumentVisibility | string;
  version: number;
  checksum?: string | null;
  tags: string[];
  description?: string | null;
  is_favorited: boolean;
  duplicate_of?: string | null;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
  versions: DocumentVersion[];
}

export interface DocumentListData {
  items: DocumentItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface DocumentUploadResult {
  document: DocumentItem;
  duplicate_detected: boolean;
  message: string;
}

export interface FolderItem {
  id: string;
  name: string;
  parent_id?: string | null;
  owner_id: string;
  company_id?: string | null;
  description?: string | null;
  created_at: string;
  updated_at: string;
}

export interface BreadcrumbItem {
  id: string;
  name: string;
}

export interface FolderTreeData {
  folders: FolderItem[];
  breadcrumb: BreadcrumbItem[];
}

export interface DocumentPreview {
  id: string;
  filename: string;
  extension: string;
  mime_type: string;
  size: number;
  owner_id: string;
  owner_name?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  version: number;
  checksum?: string | null;
  tags: string[];
  description?: string | null;
  status: string;
  visibility: string;
  pages?: number | null;
  preview_type: string;
  content?:
    | string
    | { headers: string[]; rows: string[][]; truncated?: boolean }
    | null;
  thumbnail_path?: string | null;
}
