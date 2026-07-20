import { Folder, FolderOpen, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/common/Button";
import type { BreadcrumbItem, FolderItem } from "@/types";
import { cn } from "@/lib/utils";

interface FolderTreeProps {
  folders: FolderItem[];
  breadcrumb: BreadcrumbItem[];
  currentFolderId: string | null;
  onNavigate: (folderId: string | null) => void;
  onCreate: () => void;
  onDelete?: (folder: FolderItem) => void;
  className?: string;
}

export function FolderTree({
  folders,
  breadcrumb,
  currentFolderId,
  onNavigate,
  onCreate,
  onDelete,
  className,
}: FolderTreeProps) {
  return (
    <aside
      className={cn(
        "flex h-full flex-col rounded-xl border border-border bg-card",
        className
      )}
    >
      <div className="flex items-center justify-between border-b border-border px-3 py-3">
        <h2 className="text-sm font-semibold">Folders</h2>
        <Button variant="ghost" size="icon" onClick={onCreate} aria-label="New folder">
          <Plus className="h-4 w-4" />
        </Button>
      </div>

      <nav className="border-b border-border px-2 py-2 text-xs text-muted-foreground">
        <button
          type="button"
          className="hover:text-foreground"
          onClick={() => onNavigate(null)}
        >
          All files
        </button>
        {breadcrumb.map((item) => (
          <span key={item.id}>
            {" / "}
            <button
              type="button"
              className="hover:text-foreground"
              onClick={() => onNavigate(item.id)}
            >
              {item.name}
            </button>
          </span>
        ))}
      </nav>

      <div className="flex-1 space-y-0.5 overflow-y-auto p-2">
        <button
          type="button"
          onClick={() => onNavigate(null)}
          className={cn(
            "flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm hover:bg-accent",
            currentFolderId === null && "bg-primary/10 text-primary"
          )}
        >
          <FolderOpen className="h-4 w-4" />
          Root
        </button>
        {folders.map((folder) => (
          <div
            key={folder.id}
            className={cn(
              "group flex items-center gap-1 rounded-lg hover:bg-accent",
              currentFolderId === folder.id && "bg-primary/10 text-primary"
            )}
          >
            <button
              type="button"
              className="flex flex-1 items-center gap-2 px-2 py-2 text-left text-sm"
              onClick={() => onNavigate(folder.id)}
            >
              <Folder className="h-4 w-4 shrink-0" />
              <span className="truncate">{folder.name}</span>
            </button>
            {onDelete ? (
              <button
                type="button"
                className="mr-1 hidden rounded p-1 text-muted-foreground hover:text-destructive group-hover:block"
                onClick={() => onDelete(folder)}
                aria-label={`Delete ${folder.name}`}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            ) : null}
          </div>
        ))}
        {folders.length === 0 ? (
          <p className="px-2 py-4 text-xs text-muted-foreground">No subfolders</p>
        ) : null}
      </div>
    </aside>
  );
}
