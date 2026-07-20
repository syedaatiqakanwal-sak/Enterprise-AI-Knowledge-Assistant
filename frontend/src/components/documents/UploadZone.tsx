import { useCallback, useRef, useState, type DragEvent, type ReactNode } from "react";
import { UploadCloud } from "lucide-react";
import { cn } from "@/lib/utils";

interface UploadZoneProps {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
  accept?: string;
  multiple?: boolean;
  children?: ReactNode;
  className?: string;
}

export function UploadZone({
  onFiles,
  disabled,
  accept,
  multiple = true,
  children,
  className,
}: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handleFiles = useCallback(
    (list: FileList | null) => {
      if (!list || disabled) return;
      onFiles(Array.from(list));
    },
    [disabled, onFiles]
  );

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  return (
    <div
      className={cn(
        "relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-border bg-card/40 px-6 py-10 text-center transition-colors",
        dragging && "border-primary bg-primary/5",
        disabled && "opacity-60",
        className
      )}
      onDragEnter={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      <UploadCloud className="mb-3 h-10 w-10 text-primary" />
      <p className="font-medium">Drag & drop files here</p>
      <p className="mt-1 text-sm text-muted-foreground">
        PDF, DOCX, TXT, CSV, XLSX, PPTX, images, ZIP
      </p>
      <button
        type="button"
        className="mt-4 text-sm font-medium text-primary hover:underline"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
      >
        Browse files
      </button>
      {children}
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        multiple={multiple}
        accept={accept}
        disabled={disabled}
        onChange={(e) => handleFiles(e.target.files)}
      />
    </div>
  );
}
