import { api, tokenStore } from "./client";
import type {
  ApiResponse,
  DocumentItem,
  DocumentListData,
  DocumentPreview,
  DocumentUploadResult,
  FolderItem,
  FolderTreeData,
} from "@/types";

export interface DocumentListParams {
  folder_id?: string | null;
  extension?: string;
  file_type?: string;
  tag?: string;
  visibility?: string;
  q?: string;
  date_preset?: string;
  status?: string;
  include_archived?: boolean;
  limit?: number;
  offset?: number;
}

export const documentsApi = {
  list(params?: DocumentListParams) {
    return api.get<ApiResponse<DocumentListData>>("/documents", { params });
  },
  search(params: DocumentListParams & { q: string }) {
    return api.get<ApiResponse<DocumentListData>>("/documents/search", { params });
  },
  recent(limit = 20) {
    return api.get<ApiResponse<DocumentListData>>("/documents/recent", {
      params: { limit },
    });
  },
  favorites(params?: { limit?: number; offset?: number }) {
    return api.get<ApiResponse<DocumentListData>>("/documents/favorites", {
      params,
    });
  },
  get(id: string) {
    return api.get<ApiResponse<DocumentItem>>(`/documents/${id}`);
  },
  update(
    id: string,
    payload: {
      filename?: string;
      description?: string;
      visibility?: string;
      folder_id?: string | null;
      move_to_root?: boolean;
      tags?: string[];
    }
  ) {
    return api.put<ApiResponse<DocumentItem>>(`/documents/${id}`, payload);
  },
  remove(id: string) {
    return api.delete<ApiResponse<null>>(`/documents/${id}`);
  },
  restore(id: string) {
    return api.post<ApiResponse<DocumentItem>>(`/documents/${id}/restore`);
  },
  archive(id: string) {
    return api.post<ApiResponse<DocumentItem>>(`/documents/${id}/archive`);
  },
  favorite(id: string) {
    return api.post<ApiResponse<DocumentItem>>(`/documents/${id}/favorite`);
  },
  preview(id: string) {
    return api.get<ApiResponse<{ preview: DocumentPreview }>>(
      `/documents/${id}/preview`
    );
  },
  copy(id: string, payload?: { folder_id?: string | null; move_to_root?: boolean }) {
    return api.post<ApiResponse<DocumentItem>>(`/documents/${id}/copy`, payload ?? {});
  },
  move(id: string, payload: { folder_id?: string | null; move_to_root?: boolean }) {
    return api.post<ApiResponse<DocumentItem>>(`/documents/${id}/move`, payload);
  },
  async upload(
    file: File,
    options?: {
      folder_id?: string | null;
      visibility?: string;
      description?: string;
      tags?: string;
      onProgress?: (pct: number) => void;
    }
  ) {
    const form = new FormData();
    form.append("file", file);
    if (options?.folder_id) form.append("folder_id", options.folder_id);
    if (options?.visibility) form.append("visibility", options.visibility);
    if (options?.description) form.append("description", options.description);
    if (options?.tags) form.append("tags", options.tags);

    return api.post<ApiResponse<DocumentUploadResult>>("/documents/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (event) => {
        if (!options?.onProgress || !event.total) return;
        options.onProgress(Math.round((event.loaded / event.total) * 100));
      },
    });
  },
  async download(id: string, filename: string) {
    const response = await api.get(`/documents/${id}/download`, {
      responseType: "blob",
    });
    const url = window.URL.createObjectURL(response.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    window.URL.revokeObjectURL(url);
  },
  /** Absolute download URL for image preview (uses Bearer via fetch blob instead). */
  async fetchBlob(id: string): Promise<Blob> {
    const response = await api.get(`/documents/${id}/download`, {
      responseType: "blob",
    });
    return response.data;
  },
};

export const foldersApi = {
  list(params?: { parent_id?: string | null; flat?: boolean }) {
    return api.get<ApiResponse<FolderTreeData>>("/folders", { params });
  },
  create(payload: {
    name: string;
    parent_id?: string | null;
    description?: string;
  }) {
    return api.post<ApiResponse<FolderItem>>("/folders", payload);
  },
  update(
    id: string,
    payload: {
      name?: string;
      parent_id?: string | null;
      description?: string;
      move_to_root?: boolean;
    }
  ) {
    return api.put<ApiResponse<FolderItem>>(`/folders/${id}`, payload);
  },
  remove(id: string) {
    return api.delete<ApiResponse<null>>(`/folders/${id}`);
  },
};

// Keep tokenStore accessible for rare direct Authorization needs
export { tokenStore };
