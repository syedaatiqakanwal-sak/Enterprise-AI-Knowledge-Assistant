import { useCallback, useEffect, useRef, useState } from "react";
import { Eye, Image as ImageIcon, UploadCloud } from "lucide-react";
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
import { Loader } from "@/components/common/Loader";
import { getErrorMessage } from "@/services/api/client";
import { visionApi, type VisionAnalysis } from "@/services/api/ocr";
import { cn } from "@/lib/utils";

export function VisionPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [result, setResult] = useState<VisionAnalysis | null>(null);
  const [history, setHistory] = useState<
    Array<{ id: string; filename: string; caption?: string; object_count: number }>
  >([]);

  const loadHistory = useCallback(async () => {
    try {
      const { data } = await visionApi.history({ limit: 10 });
      if (data.success && data.data) setHistory(data.data.items);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  const processFile = async (file: File, mode: "analyze" | "detect") => {
    setLoading(true);
    setResult(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(file));
    try {
      const { data } =
        mode === "detect"
          ? await visionApi.detect(file)
          : await visionApi.analyze(file);
      if (!data.success || !data.data) throw new Error(data.message || "Failed");
      setResult(data.data);
      toast.success(mode === "detect" ? "Detection complete" : "Vision analysis complete");
      await loadHistory();
    } catch (err) {
      toast.error(getErrorMessage(err, "Vision analysis failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl font-bold tracking-tight">
          Vision Intelligence
        </h1>
        <p className="mt-1 text-muted-foreground">
          Captions, scene understanding, and pluggable YOLO object detection
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Eye className="h-5 w-5 text-primary" />
                Upload image
              </CardTitle>
              <CardDescription>
                Screenshots, charts, photos, diagrams
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div
                className={cn(
                  "flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-border px-6 py-10 text-center",
                  dragging && "border-primary bg-primary/5"
                )}
                onDragEnter={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragOver={(e) => e.preventDefault()}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragging(false);
                  const f = e.dataTransfer.files?.[0];
                  if (f) void processFile(f, "analyze");
                }}
              >
                <UploadCloud className="mb-3 h-10 w-10 text-primary" />
                <p className="font-medium">Drop an image to analyze</p>
                <div className="mt-4 flex gap-2">
                  <Button
                    size="sm"
                    onClick={() => {
                      inputRef.current?.setAttribute("data-mode", "analyze");
                      inputRef.current?.click();
                    }}
                  >
                    Analyze
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      inputRef.current?.setAttribute("data-mode", "detect");
                      inputRef.current?.click();
                    }}
                  >
                    Detect objects
                  </Button>
                </div>
                <input
                  ref={inputRef}
                  type="file"
                  className="hidden"
                  accept="image/*"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    const mode =
                      inputRef.current?.getAttribute("data-mode") === "detect"
                        ? "detect"
                        : "analyze";
                    if (f) void processFile(f, mode);
                  }}
                />
              </div>

              {previewUrl ? (
                <div className="relative overflow-hidden rounded-xl border border-border">
                  <img
                    src={previewUrl}
                    alt="Vision preview"
                    className="max-h-96 w-full object-contain bg-muted/20"
                  />
                  {result?.objects?.map((o, i) => {
                    if (!o.bbox || o.bbox.length < 4) return null;
                    const [x1, y1, x2, y2] = o.bbox;
                    return (
                      <div
                        key={i}
                        className="pointer-events-none absolute border-2 border-emerald-400"
                        style={{
                          left: `${(x1 / 640) * 100}%`,
                          top: `${(y1 / 480) * 100}%`,
                          width: `${((x2 - x1) / 640) * 100}%`,
                          height: `${((y2 - y1) / 480) * 100}%`,
                        }}
                      >
                        <span className="absolute -top-5 left-0 bg-emerald-500 px-1 text-[10px] text-white">
                          {o.label} {(o.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    );
                  })}
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <Loader label="Running vision models…" />
              ) : !result ? (
                <p className="py-10 text-center text-sm text-muted-foreground">
                  Upload an image to see caption, scene, and detections
                </p>
              ) : (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-sm font-semibold">Caption</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {result.caption || "—"}
                    </p>
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold">Scene description</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {result.scene_description || "—"}
                    </p>
                  </div>
                  {result.chart_summary ? (
                    <div>
                      <h3 className="text-sm font-semibold">Chart understanding</h3>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {result.chart_summary}
                      </p>
                    </div>
                  ) : null}
                  {result.screenshot_explanation ? (
                    <div>
                      <h3 className="text-sm font-semibold">Screenshot explanation</h3>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {result.screenshot_explanation}
                      </p>
                    </div>
                  ) : null}
                  <div>
                    <h3 className="mb-2 text-sm font-semibold">Detected objects</h3>
                    <div className="overflow-auto rounded-lg border border-border">
                      <table className="w-full text-sm">
                        <thead className="bg-muted/40 text-xs uppercase text-muted-foreground">
                          <tr>
                            <th className="px-3 py-2 text-left">Label</th>
                            <th className="px-3 py-2 text-right">Confidence</th>
                            <th className="px-3 py-2 text-left">Model</th>
                          </tr>
                        </thead>
                        <tbody>
                          {result.objects.map((o, i) => (
                            <tr key={i} className="border-t border-border">
                              <td className="px-3 py-2">
                                <Badge variant="secondary">{o.label}</Badge>
                              </td>
                              <td className="px-3 py-2 text-right">
                                {(o.confidence * 100).toFixed(1)}%
                              </td>
                              <td className="px-3 py-2 text-muted-foreground">
                                {o.model_name}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ImageIcon className="h-4 w-4" />
              Recent analyses
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {history.length === 0 ? (
              <p className="text-xs text-muted-foreground">No history yet</p>
            ) : (
              history.map((h) => (
                <button
                  key={h.id}
                  type="button"
                  className="w-full rounded-lg border border-border px-3 py-2 text-left text-sm hover:bg-accent"
                  onClick={async () => {
                    try {
                      const { data } = await visionApi.get(h.id);
                      if (data.success && data.data) setResult(data.data);
                    } catch (err) {
                      toast.error(getErrorMessage(err));
                    }
                  }}
                >
                  <p className="truncate font-medium">{h.filename}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {h.object_count} objects · {h.caption || "No caption"}
                  </p>
                </button>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
