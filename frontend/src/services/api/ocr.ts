import { api } from "./client";
import type { ApiResponse } from "@/types";

export interface OCRResult {
  id: string;
  filename: string;
  status: string;
  document_type: string;
  raw_text: string;
  average_confidence: number;
  provider?: string | null;
  boxes: Array<{
    text: string;
    confidence: number;
    bbox: number[][];
    page?: number;
  }>;
  tables: unknown[];
  key_values: Record<string, string>;
  layout: Record<string, unknown>;
  structured_json: Record<string, unknown>;
  metrics: Record<string, unknown>;
  linked_document_id?: string | null;
  thumbnail_path?: string | null;
  created_at?: string | null;
}

export interface VisionObject {
  id?: string;
  label: string;
  confidence: number;
  bbox?: number[] | null;
  model_name: string;
}

export interface VisionAnalysis {
  id: string;
  filename: string;
  status: string;
  caption?: string | null;
  scene_description?: string | null;
  chart_summary?: string | null;
  screenshot_explanation?: string | null;
  provider?: string | null;
  metrics: Record<string, unknown>;
  objects: VisionObject[];
  created_at?: string | null;
}

export const ocrApi = {
  upload(file: File) {
    const form = new FormData();
    form.append("file", file);
    return api.post<ApiResponse<OCRResult>>("/ocr/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  get(id: string) {
    return api.get<ApiResponse<OCRResult>>(`/ocr/${id}`);
  },
  list(params?: { q?: string; document_type?: string; limit?: number }) {
    return api.get<
      ApiResponse<{ items: OCRResult[]; total: number; limit: number; offset: number }>
    >("/ocr", { params });
  },
  search(q: string) {
    return api.get<
      ApiResponse<{ items: OCRResult[]; total: number; limit: number; offset: number }>
    >("/ocr/search", { params: { q } });
  },
};

export const visionApi = {
  analyze(file: File) {
    const form = new FormData();
    form.append("file", file);
    return api.post<ApiResponse<VisionAnalysis>>("/vision/analyze", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  detect(file: File) {
    const form = new FormData();
    form.append("file", file);
    return api.post<ApiResponse<VisionAnalysis>>("/vision/detect", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  history(params?: { limit?: number; offset?: number }) {
    return api.get<
      ApiResponse<{
        items: Array<{
          id: string;
          filename: string;
          caption?: string;
          object_count: number;
          created_at?: string;
        }>;
        total: number;
      }>
    >("/vision/history", { params });
  },
  get(id: string) {
    return api.get<ApiResponse<VisionAnalysis>>(`/vision/${id}`);
  },
};
