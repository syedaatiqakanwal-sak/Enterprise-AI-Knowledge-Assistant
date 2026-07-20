import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  Bot,
  Copy,
  FileText,
  MessageSquare,
  Paperclip,
  Pin,
  Plus,
  RefreshCw,
  Search,
  Send,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/common/Button";
import { Input } from "@/components/common/Input";
import { Badge } from "@/components/common/Badge";
import { Loader } from "@/components/common/Loader";
import { getErrorMessage } from "@/services/api/client";
import {
  chatApi,
  type ChatMessage,
  type ChatSession,
  type Citation,
} from "@/services/api/chat";
import { documentsApi } from "@/services/api/documents";
import { useAuth } from "@/contexts/AuthContext";
import { cn, initials } from "@/lib/utils";

const SUGGESTIONS = [
  "What is our remote work policy?",
  "Summarize the employee handbook",
  "What are the vacation accrual rules?",
  "List security compliance requirements",
];

type UploadStatus = "uploading" | "processing" | "ready" | "failed";

interface ChatUpload {
  id: string;
  name: string;
  status: UploadStatus;
  progress: number;
}

export function ChatPage() {
  const { user } = useAuth();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [sending, setSending] = useState(false);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [searchQ, setSearchQ] = useState("");
  const [uploads, setUploads] = useState<ChatUpload[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const lastQuestion = useRef<string>("");

  const loadHistory = useCallback(async (q?: string) => {
    setLoadingHistory(true);
    try {
      const { data } = await chatApi.history({ q: q || undefined, limit: 50 });
      if (data.success && data.data) {
        setSessions(data.data.items);
      }
    } catch (err) {
      toast.error(getErrorMessage(err) || "Failed to load chats");
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  const openChat = useCallback(async (id: string) => {
    setActiveId(id);
    try {
      const { data } = await chatApi.get(id);
      if (data.success && data.data) {
        setMessages(data.data.messages ?? []);
        const lastAssistant = [...(data.data.messages ?? [])]
          .reverse()
          .find((m) => m.role === "assistant");
        setCitations((lastAssistant?.citations as Citation[]) ?? []);
      }
    } catch (err) {
      toast.error(getErrorMessage(err) || "Failed to open chat");
    }
  }, []);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending, uploads]);

  const startNew = () => {
    setActiveId(null);
    setMessages([]);
    setCitations([]);
    setInput("");
  };

  const send = async (text?: string) => {
    const message = (text ?? input).trim();
    if (!message || sending) return;
    lastQuestion.current = message;
    setInput("");
    setSending(true);

    const optimistic: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: message,
      created_at: new Date().toISOString(),
    };
    setMessages((m) => [...m, optimistic]);

    try {
      const { data } = await chatApi.ask({
        message,
        chat_id: activeId,
      });
      if (!data.success || !data.data) {
        throw new Error(data.message || "Chat failed");
      }
      setActiveId(data.data.chat_id);
      setMessages((prev) => {
        const withoutOptimistic = prev.filter((m) => m.id !== optimistic.id);
        return [
          ...withoutOptimistic,
          data.data!.user_message,
          data.data!.assistant_message,
        ];
      });
      setCitations(data.data.citations ?? []);
      await loadHistory();
    } catch (err) {
      toast.error(getErrorMessage(err) || "Failed to get answer");
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
    } finally {
      setSending(false);
    }
  };

  const onPickFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    for (const file of Array.from(files)) {
      const localId = crypto.randomUUID();
      setUploads((u) => [
        ...u,
        { id: localId, name: file.name, status: "uploading", progress: 0 },
      ]);
      try {
        const { data } = await documentsApi.upload(file, {
          visibility: "private",
          description: "Uploaded from chat",
          onProgress: (pct) =>
            setUploads((list) =>
              list.map((x) =>
                x.id === localId ? { ...x, progress: pct } : x,
              ),
            ),
        });
        if (!data.success) throw new Error(data.message || "Upload failed");
        setUploads((list) =>
          list.map((x) =>
            x.id === localId
              ? { ...x, status: "processing", progress: 100 }
              : x,
          ),
        );
        // Backend enqueues RAG index automatically after upload
        setTimeout(() => {
          setUploads((list) =>
            list.map((x) =>
              x.id === localId ? { ...x, status: "ready" } : x,
            ),
          );
        }, 1500);
        toast.success(`${file.name} uploaded — indexing for chat`);
      } catch (err) {
        setUploads((list) =>
          list.map((x) =>
            x.id === localId ? { ...x, status: "failed" } : x,
          ),
        );
        toast.error(getErrorMessage(err) || `Failed to upload ${file.name}`);
      }
    }
    if (fileRef.current) fileRef.current.value = "";
  };

  const togglePin = async (session: ChatSession) => {
    try {
      await chatApi.update(session.id, { is_pinned: !session.is_pinned });
      await loadHistory(searchQ);
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const removeChat = async (session: ChatSession) => {
    if (!window.confirm(`Delete "${session.title}"?`)) return;
    try {
      await chatApi.remove(session.id);
      if (activeId === session.id) startNew();
      await loadHistory(searchQ);
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const copyText = async (text: string) => {
    await navigator.clipboard.writeText(text);
    toast.success("Copied");
  };

  const pinned = sessions.filter((s) => s.is_pinned);
  const recent = sessions.filter((s) => !s.is_pinned);

  return (
    <div className="flex h-full min-h-0 overflow-hidden bg-background">
      <aside className="hidden w-72 shrink-0 flex-col border-r border-border bg-card/40 md:flex">
        <div className="space-y-2 border-b border-border p-3">
          <Button className="w-full" onClick={startNew}>
            <Plus className="h-4 w-4" />
            New chat
          </Button>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void loadHistory(searchQ)}
              placeholder="Search chats…"
              className="h-9 pl-8 text-sm"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {loadingHistory ? (
            <Loader label="Loading…" />
          ) : sessions.length === 0 ? (
            <p className="px-2 py-6 text-center text-xs text-muted-foreground">
              No conversations yet
            </p>
          ) : (
            <>
              {pinned.length > 0 && (
                <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Pinned
                </p>
              )}
              {[...pinned, ...recent].map((s) => (
                <div
                  key={s.id}
                  className={cn(
                    "group mb-1 flex items-start gap-1 rounded-lg px-2 py-2 hover:bg-accent",
                    activeId === s.id && "bg-primary/10",
                  )}
                >
                  <button
                    type="button"
                    className="min-w-0 flex-1 text-left"
                    onClick={() => void openChat(s.id)}
                  >
                    <div className="flex items-center gap-1">
                      {s.is_pinned ? (
                        <Pin className="h-3 w-3 text-primary" />
                      ) : (
                        <MessageSquare className="h-3 w-3 text-muted-foreground" />
                      )}
                      <span className="truncate text-sm font-medium">{s.title}</span>
                    </div>
                    <p className="mt-0.5 text-[11px] text-muted-foreground">
                      {new Date(s.updated_at).toLocaleString()}
                    </p>
                  </button>
                  <button
                    type="button"
                    className="hidden rounded p-1 text-muted-foreground hover:text-foreground group-hover:block"
                    onClick={() => void togglePin(s)}
                  >
                    <Pin className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    className="hidden rounded p-1 text-muted-foreground hover:text-destructive group-hover:block"
                    onClick={() => void removeChat(s)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </>
          )}
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-6">
          {messages.length === 0 && !sending ? (
            <div className="mx-auto max-w-2xl text-center">
              <Bot className="mx-auto mb-4 h-12 w-12 text-primary" />
              <h2 className="font-display text-2xl font-semibold">
                How can I help today?
              </h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Ask about your company knowledge — or attach a file to teach the
                assistant (stored & indexed automatically).
              </p>
              <div className="mt-6 grid gap-2 sm:grid-cols-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    className="rounded-xl border border-border bg-card px-3 py-3 text-left text-sm hover:border-primary/40 hover:bg-accent"
                    onClick={() => void send(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m) => (
              <div
                key={m.id}
                className={cn(
                  "mx-auto flex max-w-3xl gap-3",
                  m.role === "user" ? "justify-end" : "justify-start",
                )}
              >
                {m.role !== "user" ? (
                  <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <Bot className="h-4 w-4" />
                  </div>
                ) : null}
                <div
                  className={cn(
                    "rounded-2xl px-4 py-3 text-sm leading-relaxed",
                    m.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted/50 text-foreground",
                  )}
                >
                  {m.role === "assistant" ? (
                    <>
                      <div className="prose prose-sm dark:prose-invert max-w-none">
                        <ReactMarkdown>{m.content}</ReactMarkdown>
                      </div>
                      <div className="mt-2 flex gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 px-2"
                          onClick={() => void copyText(m.content)}
                        >
                          <Copy className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 px-2"
                          onClick={() =>
                            lastQuestion.current && void send(lastQuestion.current)
                          }
                        >
                          <RefreshCw className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </>
                  ) : (
                    m.content
                  )}
                </div>
                {m.role === "user" ? (
                  <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-semibold">
                    {initials(user?.full_name || "U")}
                  </div>
                ) : null}
              </div>
            ))
          )}
          {sending ? (
            <div className="mx-auto flex max-w-3xl items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary">
                <Bot className="h-4 w-4" />
              </div>
              <div className="flex gap-1 rounded-2xl bg-muted/50 px-4 py-3">
                <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.2s]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.1s]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground" />
              </div>
            </div>
          ) : null}
          {uploads.length > 0 && (
            <div className="mx-auto max-w-3xl space-y-2">
              {uploads.map((u) => (
                <div
                  key={u.id}
                  className="flex items-center gap-3 rounded-xl border border-border bg-card px-3 py-2 text-sm"
                >
                  <FileText className="h-4 w-4 text-primary" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{u.name}</p>
                    <p className="text-xs capitalize text-muted-foreground">
                      {u.status === "uploading"
                        ? `Uploading… ${u.progress}%`
                        : u.status === "processing"
                          ? "Processing…"
                          : u.status}
                    </p>
                  </div>
                  <Badge>{u.status}</Badge>
                </div>
              ))}
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="border-t border-border p-4">
          <div className="mx-auto flex max-w-3xl gap-2">
            <input
              ref={fileRef}
              type="file"
              className="hidden"
              multiple
              accept=".pdf,.doc,.docx,.txt,.csv,.pptx,.xlsx,.png,.jpg,.jpeg,.webp"
              onChange={(e) => void onPickFiles(e.target.files)}
            />
            <Button
              type="button"
              size="icon"
              variant="outline"
              className="h-11 w-11 shrink-0"
              onClick={() => fileRef.current?.click()}
              aria-label="Attach file"
            >
              <Paperclip className="h-4 w-4" />
            </Button>
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
              placeholder="Message the knowledge assistant…"
              disabled={sending}
              className="h-11"
            />
            <Button
              size="icon"
              className="h-11 w-11 shrink-0"
              disabled={sending || !input.trim()}
              onClick={() => void send()}
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </section>

      <aside className="hidden w-80 shrink-0 flex-col border-l border-border lg:flex">
        <div className="border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold">Sources</h2>
          <p className="text-xs text-muted-foreground">
            Citations from the latest answer
          </p>
        </div>
        <div className="flex-1 space-y-3 overflow-y-auto p-3">
          {citations.length === 0 ? (
            <p className="px-1 py-8 text-center text-xs text-muted-foreground">
              Citations appear here after you ask a question.
            </p>
          ) : (
            citations.map((c, idx) => (
              <div
                key={`${c.document_id}-${c.chunk_index}-${idx}`}
                className="rounded-xl border border-border bg-card p-3"
              >
                <div className="mb-2 flex items-start gap-2">
                  <FileText className="mt-0.5 h-4 w-4 text-primary" />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{c.filename}</p>
                    <p className="text-[11px] text-muted-foreground">
                      {c.page != null ? `Page ${c.page}` : "Page —"} · Chunk{" "}
                      {c.chunk_index}
                    </p>
                  </div>
                </div>
                <p className="line-clamp-4 text-xs text-muted-foreground">
                  {c.snippet}
                </p>
              </div>
            ))
          )}
        </div>
      </aside>
    </div>
  );
}
