import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2,
  Clock,
  FileAudio,
  ListChecks,
  MessageSquare,
  Mic,
  Search,
  Trash2,
  Upload,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/common/Card";
import { ProgressBar } from "@/components/documents/ProgressBar";
import { getErrorMessage } from "@/services/api/client";
import {
  meetingsApi,
  type Meeting,
  type MeetingChatMessage,
} from "@/services/api/meetings";
import { cn } from "@/lib/utils";

function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toString().padStart(2, "0")}`;
}

function formatTs(seconds: number): string {
  const s = Math.floor(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h > 0) {
    return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${r
      .toString()
      .padStart(2, "0")}`;
  }
  return `${m.toString().padStart(2, "0")}:${r.toString().padStart(2, "0")}`;
}

const ACCEPT =
  ".mp3,.wav,.m4a,.aac,.flac,.ogg,.mp4,.mov,.mkv,.avi,audio/*,video/*";

export function MeetingsPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Meeting | null>(null);
  const [search, setSearch] = useState("");
  const [transcriptFilter, setTranscriptFilter] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatHistory, setChatHistory] = useState<MeetingChatMessage[]>([]);

  const loadList = useCallback(async (q?: string) => {
    const { data } = await meetingsApi.list({ q: q || undefined, limit: 50 });
    if (data.success && data.data) {
      setMeetings(data.data.items);
      return data.data.items;
    }
    return [];
  }, []);

  const loadDetail = useCallback(async (id: string) => {
    const { data } = await meetingsApi.get(id);
    if (data.success && data.data) {
      setDetail(data.data);
      setChatHistory(data.data.chat_messages || []);
      setSelectedId(id);
    }
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const items = await loadList();
        if (items[0]) await loadDetail(items[0].id);
      } catch (err) {
        toast.error(getErrorMessage(err, "Failed to load meetings"));
      }
    })();
  }, [loadList, loadDetail]);

  const processFile = async (file: File) => {
    setLoading(true);
    setProgress(20);
    try {
      setProgress(45);
      const { data } = await meetingsApi.upload(file, { autoProcess: true });
      setProgress(90);
      if (!data.success || !data.data) throw new Error(data.message || "Upload failed");
      toast.success(
        data.data.linked_document_id
          ? "Meeting processed — transcript indexed for chat"
          : "Meeting processed"
      );
      await loadList(search);
      await loadDetail(data.data.id);
      setProgress(100);
    } catch (err) {
      toast.error(getErrorMessage(err, "Meeting upload failed"));
    } finally {
      setLoading(false);
    }
  };

  const onSearch = async () => {
    try {
      const items = await loadList(search);
      if (items[0]) await loadDetail(items[0].id);
      else {
        setDetail(null);
        setSelectedId(null);
      }
    } catch (err) {
      toast.error(getErrorMessage(err, "Search failed"));
    }
  };

  const sendChat = async () => {
    if (!selectedId || !chatInput.trim()) return;
    setChatBusy(true);
    try {
      const { data } = await meetingsApi.chat(selectedId, chatInput.trim());
      if (!data.success || !data.data) throw new Error(data.message || "Chat failed");
      setChatHistory(data.data.history || []);
      setChatInput("");
    } catch (err) {
      toast.error(getErrorMessage(err, "Meeting chat failed"));
    } finally {
      setChatBusy(false);
    }
  };

  const removeMeeting = async (id: string) => {
    try {
      await meetingsApi.remove(id);
      toast.success("Meeting deleted");
      const items = await loadList(search);
      if (items[0]) await loadDetail(items[0].id);
      else {
        setDetail(null);
        setSelectedId(null);
        setChatHistory([]);
      }
    } catch (err) {
      toast.error(getErrorMessage(err, "Delete failed"));
    }
  };

  const filteredSegments = useMemo(() => {
    const segs = detail?.segments || [];
    const q = transcriptFilter.trim().toLowerCase();
    if (!q) return segs;
    return segs.filter(
      (s) =>
        s.text.toLowerCase().includes(q) || s.speaker.toLowerCase().includes(q)
    );
  }, [detail?.segments, transcriptFilter]);

  const maxTalk = Math.max(
    1,
    ...(detail?.speakers || []).map((s) => s.talk_time_seconds || 0)
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl font-bold tracking-tight">
          Meeting Intelligence
        </h1>
        <p className="mt-1 text-muted-foreground">
          Transcribe, diarize, summarize, and chat with meeting recordings
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[320px_1fr]">
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Upload className="h-4 w-4 text-primary" />
                Upload recording
              </CardTitle>
              <CardDescription>
                MP3, WAV, M4A, AAC, FLAC, OGG, MP4, MOV, MKV, AVI
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div
                className={cn(
                  "flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-border px-4 py-10 text-center transition",
                  dragOver && "border-primary bg-primary/5"
                )}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  const f = e.dataTransfer.files?.[0];
                  if (f) void processFile(f);
                }}
              >
                <Mic className="mb-3 h-8 w-8 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  Drag & drop audio or video
                </p>
                <Button
                  className="mt-4"
                  size="sm"
                  disabled={loading}
                  onClick={() => inputRef.current?.click()}
                >
                  Choose file
                </Button>
                <input
                  ref={inputRef}
                  type="file"
                  accept={ACCEPT}
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) void processFile(f);
                    e.target.value = "";
                  }}
                />
              </div>
              {loading && (
                <div className="mt-4 space-y-2">
                  <ProgressBar value={progress} />
                  <p className="text-xs text-muted-foreground">
                    Running Whisper → diarization → analysis → RAG index…
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Meeting history</CardTitle>
              <div className="flex gap-2 pt-2">
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && void onSearch()}
                  placeholder="Search name, keyword…"
                  className="h-9 flex-1 rounded-md border border-border bg-background px-3 text-sm"
                />
                <Button size="sm" variant="outline" onClick={() => void onSearch()}>
                  <Search className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="max-h-[420px] space-y-2 overflow-y-auto">
              {meetings.length === 0 && (
                <p className="text-sm text-muted-foreground">No meetings yet</p>
              )}
              {meetings.map((m) => {
                const isVideo = ["mp4", "mov", "mkv", "avi"].includes(m.extension);
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => void loadDetail(m.id)}
                    className={cn(
                      "flex w-full items-start gap-3 rounded-lg border border-transparent p-3 text-left transition hover:bg-muted/60",
                      selectedId === m.id && "border-border bg-muted/80"
                    )}
                  >
                    {isVideo ? (
                      <FileAudio className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                    ) : (
                      <Mic className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{m.title}</p>
                      <p className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        {formatDuration(m.duration_seconds || 0)}
                        <Badge
                          variant={m.status === "ready" ? "success" : "secondary"}
                        >
                          {m.status}
                        </Badge>
                      </p>
                    </div>
                  </button>
                );
              })}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          {!detail && !loading && (
            <Card>
              <CardContent className="py-16 text-center text-muted-foreground">
                Upload a recording to generate transcript, summary, and action items
              </CardContent>
            </Card>
          )}

          {detail && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="font-display text-xl font-semibold">{detail.title}</h2>
                  <p className="text-sm text-muted-foreground">
                    {detail.original_filename} · {formatDuration(detail.duration_seconds)} ·{" "}
                    {detail.provider || "—"}
                  </p>
                </div>
                <div className="flex gap-2">
                  {detail.linked_document_id && (
                    <Badge variant="success">
                      <CheckCircle2 className="mr-1 h-3 w-3" />
                      RAG indexed
                    </Badge>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => void removeMeeting(detail.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              {(detail.speakers?.length ?? 0) > 0 && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">Speaker timeline</CardTitle>
                  </CardHeader>
                  <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {detail.speakers!.map((s) => (
                      <div
                        key={s.label}
                        className="rounded-lg border border-border p-3"
                      >
                        <p className="text-sm font-medium">
                          {s.display_name || s.label}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {formatDuration(s.talk_time_seconds)} talk time
                        </p>
                        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full bg-primary"
                            style={{
                              width: `${(s.talk_time_seconds / maxTalk) * 100}%`,
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}

              <div className="grid gap-4 lg:grid-cols-2">
                <Card className="min-h-[320px]">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">Transcript</CardTitle>
                    <input
                      value={transcriptFilter}
                      onChange={(e) => setTranscriptFilter(e.target.value)}
                      placeholder="Filter by speaker or keyword…"
                      className="mt-2 h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
                    />
                  </CardHeader>
                  <CardContent className="max-h-[420px] space-y-3 overflow-y-auto">
                    {filteredSegments.length === 0 && (
                      <p className="text-sm text-muted-foreground">No segments</p>
                    )}
                    {filteredSegments.map((seg) => (
                      <div key={seg.id} className="text-sm">
                        <p className="font-medium text-primary">
                          [{formatTs(seg.start_time)}] {seg.speaker}
                        </p>
                        <p className="mt-0.5 text-foreground/90">{seg.text}</p>
                      </div>
                    ))}
                  </CardContent>
                </Card>

                <Card className="min-h-[320px]">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">Summary & minutes</CardTitle>
                  </CardHeader>
                  <CardContent className="max-h-[420px] space-y-4 overflow-y-auto text-sm">
                    {detail.summary ? (
                      <>
                        <div>
                          <p className="mb-1 font-medium">Executive summary</p>
                          <p className="text-muted-foreground">
                            {detail.summary.executive_summary}
                          </p>
                        </div>
                        {(detail.summary.key_points?.length ?? 0) > 0 && (
                          <div>
                            <p className="mb-1 font-medium">Key points</p>
                            <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
                              {detail.summary.key_points.map((p, i) => (
                                <li key={i}>{p}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {(detail.summary.open_questions?.length ?? 0) > 0 && (
                          <div>
                            <p className="mb-1 font-medium">Open questions</p>
                            <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
                              {detail.summary.open_questions.map((p, i) => (
                                <li key={i}>{p}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {(detail.summary.risks?.length ?? 0) > 0 && (
                          <div>
                            <p className="mb-1 font-medium">Risks</p>
                            <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
                              {detail.summary.risks.map((p, i) => (
                                <li key={i}>{p}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </>
                    ) : (
                      <p className="text-muted-foreground">Summary not ready</p>
                    )}
                  </CardContent>
                </Card>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <ListChecks className="h-4 w-4" />
                      Action items
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className="border-b border-border text-muted-foreground">
                          <th className="py-2 pr-2 font-medium">Owner</th>
                          <th className="py-2 pr-2 font-medium">Task</th>
                          <th className="py-2 pr-2 font-medium">Due</th>
                          <th className="py-2 font-medium">Priority</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(detail.action_items || []).map((a) => (
                          <tr key={a.id} className="border-b border-border/60">
                            <td className="py-2 pr-2">{a.owner || "—"}</td>
                            <td className="py-2 pr-2">{a.task}</td>
                            <td className="py-2 pr-2">{a.due_date || "—"}</td>
                            <td className="py-2">
                              <Badge variant="secondary">{a.priority}</Badge>
                            </td>
                          </tr>
                        ))}
                        {(detail.action_items || []).length === 0 && (
                          <tr>
                            <td
                              colSpan={4}
                              className="py-4 text-muted-foreground"
                            >
                              No action items
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">Decisions</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {(detail.decisions || []).map((d) => (
                      <div
                        key={d.id}
                        className="rounded-lg border border-border p-3 text-sm"
                      >
                        <p>{d.decision}</p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {d.decided_by || "—"} {d.context ? `· ${d.context}` : ""}
                        </p>
                      </div>
                    ))}
                    {(detail.decisions || []).length === 0 && (
                      <p className="text-sm text-muted-foreground">No decisions</p>
                    )}
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <MessageSquare className="h-4 w-4" />
                    Chat with meeting
                  </CardTitle>
                  <CardDescription>
                    Answers are grounded only in this meeting transcript
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="max-h-56 space-y-2 overflow-y-auto rounded-lg border border-border p-3">
                    {chatHistory.length === 0 && (
                      <p className="text-sm text-muted-foreground">
                        Try: “What are the deadlines?” or “What was decided?”
                      </p>
                    )}
                    {chatHistory.map((m) => (
                      <div
                        key={m.id}
                        className={cn(
                          "rounded-md px-3 py-2 text-sm",
                          m.role === "user" ? "bg-primary/10" : "bg-muted/60"
                        )}
                      >
                        <span className="mr-2 text-xs font-semibold uppercase text-muted-foreground">
                          {m.role}
                        </span>
                        {m.content}
                      </div>
                    ))}
                  </div>
                  <div className="flex gap-2">
                    <input
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && void sendChat()}
                      placeholder="Ask about this meeting…"
                      className="h-10 flex-1 rounded-md border border-border bg-background px-3 text-sm"
                      disabled={chatBusy || !detail.linked_document_id}
                    />
                    <Button
                      onClick={() => void sendChat()}
                      disabled={chatBusy || !detail.linked_document_id}
                    >
                      {chatBusy ? "…" : "Ask"}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
