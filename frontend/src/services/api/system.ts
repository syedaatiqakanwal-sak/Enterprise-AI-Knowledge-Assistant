import { api } from "./client";
import type { ApiResponse } from "@/types";

export interface LlmRuntimeInfo {
  provider: string;
  model: string | null;
  llm_provider_setting: string;
  embedding_provider: string;
  embedding_model: string | null;
}

export interface OllamaStatus {
  provider: string;
  reachable: boolean;
  selected_model: string | null;
  installed_models: string[];
  version: string | null;
  gpu_available: boolean | null;
  latency_ms: number | null;
  base_url?: string;
  error: string | null;
  llm_provider_setting?: string;
  embedding_provider?: string;
  test_generate?: boolean;
  test_reply_preview?: string;
}

export const systemApi = {
  llmInfo() {
    return api.get<ApiResponse<LlmRuntimeInfo>>("/system/llm");
  },
  ollamaStatus() {
    return api.get<ApiResponse<OllamaStatus>>("/system/ollama/status");
  },
  ollamaModels() {
    return api.get<
      ApiResponse<{
        models: string[];
        selected_model: string | null;
        base_url: string;
      }>
    >("/system/ollama/models");
  },
  testOllama(model?: string | null) {
    return api.post<ApiResponse<OllamaStatus>>("/system/ollama/test", {
      model: model || null,
    });
  },
  selectOllamaModel(model: string) {
    return api.post<
      ApiResponse<{
        selected_model: string | null;
        provider: string;
        installed_models: string[];
      }>
    >("/system/ollama/model", { model });
  },
};
