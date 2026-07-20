import { useCallback, useRef, useState } from "react";
import {
  Download,
  FileJson,
  FileSpreadsheet,
  FileText,
  ScanText,
  UploadCloud,
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
import { Loader } from "@/components/common/Loader";
import { ProgressBar } from "@/components/documents/ProgressBar";
import { getErrorMessage } from "@/services/api/client";
import { ocrApi, type OCRResult } from "@/services/api/ocr";
import { cn } from "@/lib/utils";

function downloadBlob(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function OCRPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [result, setResult] = useState<OCRResult | null>(null);

  const processFile = useCallback(async (file: File) => {
    setLoading(true);
    setProgress(15);
    setResult(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(file));
    try {
      setProgress(45);
      const { data } = await ocrApi.upload(file);
      setProgress(90);
      if (!data.success || !data.data) throw new Error(data.message || "OCR failed");
      setResult(data.data);
      toast.success(
        data.data.linked_document_id
          ? "OCR complete — text indexed for Chat RAG"
          : "OCR complete"
      );
      setProgress(100);
    } catch (err) {
      toast.error(getErrorMessage(err, "OCR failed"));
    } finally {
      setLoading(false);
    }
  }, [previewUrl]);

  const onFiles = (list: FileList | null) => {
    const file = list?.[0];
    if (file) void processFile(file);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl font-bold tracking-tight">
          Document Intelligence
        </h1>
        <p className="mt-1 text-muted-foreground">
          OCR, layout analysis, tables, key-values — auto-indexed into your knowledge base
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ScanText className="h-5 w-5 text-primary" />
              Upload scanned document
            </CardTitle>
            <CardDescription>
              PNG, JPG, WEBP, TIFF, BMP, scanned PDF
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div
              className={cn(
                "flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-border px-6 py-12 text-center transition",
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
                onFiles(e.dataTransfer.files);
              }}
            >
              <UploadCloud className="mb-3 h-10 w-10 text-primary" />
              <p className="font-medium">Drag & drop image or scanned PDF</p>
              <button
                type="button"
                className="mt-3 text-sm text-primary hover:underline"
                onClick={() => inputRef.current?.click()}
              >
                Browse files
              </button>
              <input
                ref={inputRef}
                type="file"
                className="hidden"
                accept=".png,.jpg,.jpeg,.webp,.tiff,.tif,.bmp,.pdf,image/*"
                onChange={(e) => onFiles(e.target.files)}
              />
            </div>
            {loading ? <ProgressBar label="Processing OCR…" value={progress} /> : null}
            {previewUrl ? (
              <div className="relative overflow-hidden rounded-xl border border-border bg-muted/20">
                <img
                  src={previewUrl}
                  alt="Preview"
                  className="max-h-80 w-full object-contain"
                />
                {result?.boxes?.length ? (
                  <svg className="pointer-events-none absolute inset-0 h-full w-full">
                    {result.boxes.slice(0, 40).map((b, i) => {
                      const xs = b.bbox.map((p) => p[0]);
                      const ys = b.bbox.map((p) => p[1]);
                      const minX = Math.min(...xs);
                      const minY = Math.min(...ys);
                      const maxX = Math.max(...xs);
                      const maxY = Math.max(...ys);
                      return (
                        <rect
                          key={i}
                          x={`${(minX / 640) * 100}%`}
                          y={`${(minY / 480) * 100}%`}
                          width={`${((maxX - minX) / 640) * 100}%`}
                          height={`${((maxY - minY) / 480) * 100}%`}
                          fill="none"
                          stroke="rgb(139 92 246)"
                          strokeWidth="1"
                        />
                      );
                    })}
                  </svg>
                ) : null}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Extraction result</CardTitle>
            <CardDescription>
              {result
                ? `${result.document_type} · ${(result.average_confidence * 100).toFixed(0)}% confidence · ${result.provider}`
                : "Run OCR to see structured output"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading && !result ? (
              <Loader label="Extracting text…" />
            ) : !result ? (
              <p className="py-12 text-center text-sm text-muted-foreground">
                No result yet
              </p>
            ) : (
              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  <Badge>{result.document_type}</Badge>
                  {result.linked_document_id ? (
                    <Badge variant="success">RAG indexed</Badge>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      downloadBlob(
                        `${result.filename}.txt`,
                        result.raw_text,
                        "text/plain"
                      )
                    }
                  >
                    <FileText className="h-4 w-4" />
                    TXT
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      downloadBlob(
                        `${result.filename}.json`,
                        JSON.stringify(result.structured_json, null, 2),
                        "application/json"
                      )
                    }
                  >
                    <FileJson className="h-4 w-4" />
                    JSON
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      const table = result.tables?.[0] as
                        | { headers?: string[]; rows?: string[][] }
                        | undefined;
                      if (!table?.headers) {
                        toast.message("No table detected");
                        return;
                      }
                      const csv = [
                        table.headers.join(","),
                        ...(table.rows || []).map((r) => r.join(",")),
                      ].join("\n");
                      downloadBlob(`${result.filename}.csv`, csv, "text/csv");
                    }}
                  >
                    <FileSpreadsheet className="h-4 w-4" />
                    CSV
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      downloadBlob(
                        `${result.filename}-full.json`,
                        JSON.stringify(result, null, 2),
                        "application/json"
                      )
                    }
                  >
                    <Download className="h-4 w-4" />
                    Full export
                  </Button>
                </div>

                <div>
                  <h3 className="mb-2 text-sm font-semibold">Key values</h3>
                  <div className="space-y-1 rounded-lg border border-border p-3 text-sm">
                    {Object.keys(result.key_values || {}).length === 0 ? (
                      <p className="text-muted-foreground">None detected</p>
                    ) : (
                      Object.entries(result.key_values).map(([k, v]) => (
                        <div key={k} className="flex justify-between gap-4">
                          <span className="text-muted-foreground">{k}</span>
                          <span className="font-medium">{v}</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                <div>
                  <h3 className="mb-2 text-sm font-semibold">Extracted text</h3>
                  <pre className="max-h-48 overflow-auto rounded-lg bg-muted/40 p-3 text-xs whitespace-pre-wrap">
                    {result.raw_text}
                  </pre>
                </div>

                <div>
                  <h3 className="mb-2 text-sm font-semibold">Confidence table</h3>
                  <div className="max-h-40 overflow-auto rounded-lg border border-border text-xs">
                    <table className="w-full">
                      <thead className="bg-muted/40">
                        <tr>
                          <th className="px-2 py-1 text-left">Text</th>
                          <th className="px-2 py-1 text-right">Conf.</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.boxes.slice(0, 30).map((b, i) => (
                          <tr key={i} className="border-t border-border">
                            <td className="px-2 py-1">{b.text}</td>
                            <td className="px-2 py-1 text-right">
                              {(b.confidence * 100).toFixed(0)}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div>
                  <h3 className="mb-2 text-sm font-semibold">Structured JSON</h3>
                  <pre className="max-h-40 overflow-auto rounded-lg bg-muted/40 p-3 text-[11px]">
                    {JSON.stringify(result.structured_json, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
