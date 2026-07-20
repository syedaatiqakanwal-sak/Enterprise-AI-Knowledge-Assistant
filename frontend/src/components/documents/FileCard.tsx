import {
  Download,
  Eye,
  File,
  FileSpreadsheet,
  FileText,
  Image as ImageIcon,
  MoreHorizontal,
  Star,
  Trash2,
  Archive,
} from "lucide-react";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import type { DocumentItem } from "@/types";
import { formatBytes } from "@/lib/utils";
import { cn } from "@/lib/utils";

function typeIcon(ext: string) {
  if (["png", "jpg", "jpeg", "webp"].includes(ext)) return ImageIcon;
  if (["xlsx", "csv"].includes(ext)) return FileSpreadsheet;
  if (["pdf", "docx", "txt", "pptx"].includes(ext)) return FileText;
  return File;
}

const statusVariant: Record<string, "success" | "warning" | "secondary" | "default"> = {
  ready: "success",
  processing: "warning",
  uploading: "warning",
  archived: "secondary",
  failed: "secondary",
  deleted: "secondary",
};

interface FileCardProps {
  doc: DocumentItem;
  selected?: boolean;
  onSelect?: () => void;
  onPreview: () => void;
  onDownload: () => void;
  onFavorite: () => void;
  onArchive: () => void;
  onDelete: () => void;
  onRename: () => void;
}

export function FileCard({
  doc,
  selected,
  onSelect,
  onPreview,
  onDownload,
  onFavorite,
  onArchive,
  onDelete,
  onRename,
}: FileCardProps) {
  const Icon = typeIcon(doc.extension);
  return (
    <div
      className={cn(
        "group relative rounded-xl border border-border bg-card p-4 transition hover:border-primary/40 hover:shadow-sm",
        selected && "border-primary ring-1 ring-primary/30"
      )}
      onClick={onSelect}
      onContextMenu={(e) => {
        e.preventDefault();
        onPreview();
      }}
    >
      <div className="mb-3 flex items-start justify-between">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="h-5 w-5" />
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 opacity-0 group-hover:opacity-100"
          onClick={(e) => {
            e.stopPropagation();
            onFavorite();
          }}
        >
          <Star
            className={cn(
              "h-4 w-4",
              doc.is_favorited && "fill-amber-400 text-amber-400"
            )}
          />
        </Button>
      </div>
      <button
        type="button"
        className="line-clamp-2 text-left text-sm font-medium hover:text-primary"
        onClick={(e) => {
          e.stopPropagation();
          onRename();
        }}
        title="Click to rename"
      >
        {doc.filename}
      </button>
      <p className="mt-1 text-xs text-muted-foreground">
        {formatBytes(doc.size)} · {doc.extension.toUpperCase()}
      </p>
      <div className="mt-3 flex items-center justify-between">
        <Badge variant={statusVariant[doc.status] ?? "secondary"}>{doc.status}</Badge>
        <div className="flex gap-0.5 opacity-0 transition group-hover:opacity-100">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={(e) => {
              e.stopPropagation();
              onPreview();
            }}
          >
            <Eye className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={(e) => {
              e.stopPropagation();
              onDownload();
            }}
          >
            <Download className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={(e) => {
              e.stopPropagation();
              onArchive();
            }}
          >
            <Archive className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-destructive"
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
      <MoreHorizontal className="pointer-events-none absolute right-3 top-3 h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-40" />
    </div>
  );
}
