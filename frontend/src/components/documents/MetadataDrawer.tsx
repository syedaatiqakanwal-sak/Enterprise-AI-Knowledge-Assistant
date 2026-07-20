import { useEffect, useState } from "react";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Drawer } from "@/components/common/Drawer";
import { Loader } from "@/components/common/Loader";
import { documentsApi } from "@/services/api/documents";
import { getErrorMessage } from "@/services/api/client";
import type { DocumentItem, DocumentPreview } from "@/types";
import { formatBytes } from "@/lib/utils";
import { toast } from "sonner";

interface MetadataDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  document: DocumentItem | null;
}

export function MetadataDrawer({
  open,
  onOpenChange,
  document: doc,
}: MetadataDrawerProps) {
  const [preview, setPreview] = useState<DocumentPreview | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !doc) return;
    let revoked: string | null = null;
    (async () => {
      setLoading(true);
      setPreview(null);
      setImageUrl(null);
      try {
        const { data } = await documentsApi.preview(doc.id);
        if (data.success && data.data) {
          setPreview(data.data.preview);
          if (data.data.preview.preview_type === "image") {
            const blob = await documentsApi.fetchBlob(doc.id);
            revoked = URL.createObjectURL(blob);
            setImageUrl(revoked);
          }
        }
      } catch (err) {
        toast.error(getErrorMessage(err, "Preview failed"));
      } finally {
        setLoading(false);
      }
    })();
    return () => {
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [open, doc]);

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={doc?.filename ?? "Document"}
      side="right"
    >
      {!doc ? null : loading ? (
        <Loader label="Loading preview…" />
      ) : (
        <div className="space-y-6">
          <section className="space-y-2 text-sm">
            <h3 className="font-semibold">Metadata</h3>
            <MetaRow label="Type" value={doc.extension.toUpperCase()} />
            <MetaRow label="Size" value={formatBytes(doc.size)} />
            <MetaRow label="Owner" value={doc.owner_name ?? "—"} />
            <MetaRow
              label="Uploaded"
              value={new Date(doc.created_at).toLocaleString()}
            />
            <MetaRow label="Version" value={`v${doc.version}`} />
            <MetaRow label="Visibility" value={doc.visibility} />
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">Status</span>
              <Badge>{doc.status}</Badge>
            </div>
            {doc.tags?.length ? (
              <div className="flex flex-wrap gap-1 pt-1">
                {doc.tags.map((t) => (
                  <Badge key={t} variant="secondary">
                    {t}
                  </Badge>
                ))}
              </div>
            ) : null}
            {doc.description ? (
              <p className="pt-2 text-muted-foreground">{doc.description}</p>
            ) : null}
            {doc.checksum ? (
              <p className="break-all font-mono text-[10px] text-muted-foreground">
                SHA-256: {doc.checksum}
              </p>
            ) : null}
          </section>

          <section>
            <h3 className="mb-2 font-semibold">Preview</h3>
            {preview?.preview_type === "image" && imageUrl ? (
              <img
                src={imageUrl}
                alt={doc.filename}
                className="max-h-80 w-full rounded-lg object-contain"
              />
            ) : null}
            {preview?.preview_type === "text" &&
            typeof preview.content === "string" ? (
              <pre className="max-h-80 overflow-auto rounded-lg bg-muted/40 p-3 text-xs">
                {preview.content}
              </pre>
            ) : null}
            {preview?.preview_type === "csv" &&
            preview.content &&
            typeof preview.content === "object" ? (
              <div className="max-h-80 overflow-auto rounded-lg border border-border">
                <table className="w-full text-xs">
                  <tbody>
                    {preview.content.rows.map((row, i) => (
                      <tr key={i} className="border-b border-border">
                        {row.map((cell, j) => (
                          <td key={j} className="px-2 py-1">
                            {cell}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            {preview?.preview_type === "docx" &&
            typeof preview.content === "string" ? (
              <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-muted/40 p-3 text-xs">
                {preview.content || "(empty document)"}
              </pre>
            ) : null}
            {preview?.preview_type === "pdf" ? (
              <p className="text-sm text-muted-foreground">
                PDF preview — download the file to view all pages.
              </p>
            ) : null}
            {preview &&
            !["image", "text", "csv", "docx", "pdf"].includes(
              preview.preview_type
            ) ? (
              <p className="text-sm text-muted-foreground">
                Preview not available for this file type. Metadata only.
              </p>
            ) : null}
          </section>

          <Button
            className="w-full"
            variant="outline"
            onClick={() => documentsApi.download(doc.id, doc.filename)}
          >
            Download
          </Button>
        </div>
      )}
    </Drawer>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  );
}
