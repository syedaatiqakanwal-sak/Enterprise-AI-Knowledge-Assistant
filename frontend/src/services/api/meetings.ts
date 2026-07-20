import { api } from "./client";
import type { ApiResponse } from "@/types";

export interface MeetingSegment {
  id: string;
  speaker: string;
  start_time: number;
  end_time: number;
  text: string;
  confidence?: number;
  words?: unknown[];
}

export interface MeetingSpeaker {
  id?: string;
  label: string;
  display_name?: string | null;
  talk_time_seconds: number;
}

export interface MeetingActionItem {
  id: string;
  owner?: string | null;
  task: string;
  due_date?: string | null;
  priority: string;
  status: string;
}

export interface MeetingDecision {
  id: string;
  decision: string;
  context?: string | null;
  decided_by?: string | null;
}

export interface MeetingSummary {
  executive_summary: string;
  key_points: string[];
  risks: string[];
  open_questions: string[];
  minutes: Record<string, unknown>;
  attendance: string[];
}

export interface MeetingChatMessage {
  id: string;
  role: string;
  content: string;
  citations?: unknown[];
}

export interface Meeting {
  id: string;
  title: string;
  original_filename: string;
  extension: string;
  mime_type?: string;
  size?: number;
  status: string;
  duration_seconds: number;
  language?: string;
  provider?: string | null;
  linked_document_id?: string | null;
  error?: string | null;
  metrics?: Record<string, unknown>;
  created_at?: string | null;
  speaker_count?: number;
  speakers?: MeetingSpeaker[];
  segments?: MeetingSegment[];
  summary?: MeetingSummary | null;
  action_items?: MeetingActionItem[];
  decisions?: MeetingDecision[];
  chat_messages?: MeetingChatMessage[];
}

export interface MeetingChatResult {
  meeting_id: string;
  message_id: string;
  answer: string;
  citations: unknown[];
  grounded: boolean;
  metrics: Record<string, unknown>;
  history: MeetingChatMessage[];
}

export const meetingsApi = {
  upload(file: File, opts?: { title?: string; autoProcess?: boolean }) {
    const form = new FormData();
    form.append("file", file);
    if (opts?.title) form.append("title", opts.title);
    form.append("auto_process", String(opts?.autoProcess ?? true));
    return api.post<ApiResponse<Meeting>>("/meetings/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  process(meetingId: string) {
    return api.post<ApiResponse<Meeting>>("/meetings/process", null, {
      params: { meeting_id: meetingId },
    });
  },
  transcribe(meetingId: string) {
    return api.post<ApiResponse<Meeting>>("/meetings/transcribe", null, {
      params: { meeting_id: meetingId },
    });
  },
  list(params?: { q?: string; speaker?: string; status?: string; limit?: number }) {
    return api.get<
      ApiResponse<{ items: Meeting[]; total: number; limit: number; offset: number }>
    >("/meetings", { params });
  },
  get(id: string) {
    return api.get<ApiResponse<Meeting>>(`/meetings/${id}`);
  },
  transcript(id: string) {
    return api.get<
      ApiResponse<{
        meeting_id: string;
        duration_seconds: number;
        language: string;
        speakers: MeetingSpeaker[];
        segments: MeetingSegment[];
      }>
    >(`/meetings/${id}/transcript`);
  },
  summary(id: string) {
    return api.get<
      ApiResponse<{
        meeting_id: string;
        executive_summary: string;
        key_points: string[];
        risks: string[];
        open_questions: string[];
        minutes: Record<string, unknown>;
        attendance: string[];
        action_items: MeetingActionItem[];
        decisions: MeetingDecision[];
        deadlines: string[];
      }>
    >(`/meetings/${id}/summary`);
  },
  chat(id: string, message: string) {
    return api.post<ApiResponse<MeetingChatResult>>(`/meetings/${id}/chat`, {
      message,
    });
  },
  remove(id: string) {
    return api.delete<ApiResponse<{ id: string }>>(`/meetings/${id}`);
  },
};
