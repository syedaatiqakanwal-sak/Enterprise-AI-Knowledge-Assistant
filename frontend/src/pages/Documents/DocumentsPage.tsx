import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Grid3X3,
  LayoutList,
  Star,
  Upload,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { Input } from "@/components/common/Input";
import { Loader } from "@/components/common/Loader";
import { Modal } from "@/components/common/Modal";
import { Pagination } from "@/components/common/Pagination";
import { SearchBar } from "@/components/common/SearchBar";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/tables/DataTable";
import { FileCard } from "@/components/documents/FileCard";
import { FolderTree } from "@/components/documents/FolderTree";
import { MetadataDrawer } from "@/components/documents/MetadataDrawer";
import { ProgressBar } from "@/components/documents/ProgressBar";
import { UploadZone } from "@/components/documents/UploadZone";
import { getErrorMessage } from "@/services/api/client";
import { documentsApi, foldersApi } from "@/services/api/documents";
import type { BreadcrumbItem, DocumentItem, FolderItem } from "@/types";
import { formatBytes } from "@/lib/utils";

const PAGE_SIZE = 12;

export function DocumentsPage() {
  const [view, setView] = useState<"grid" | "list">("grid");
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [folders, setFolders] = useState<FolderItem[]>([]);
  const [breadcrumb, setBreadcrumb] = useState<BreadcrumbItem[]>([]);
  const [folderId, setFolderId] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [fileType, setFileType] = useState("all");
  const [datePreset, setDatePreset] = useState("all");
  const [favoritesOnly, setFavoritesOnly] = useState(false);

  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<Record<string, number>>({});

  const [folderModal, setFolderModal] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");

  const [renameDoc, setRenameDoc] = useState<DocumentItem | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const [previewDoc, setPreviewDoc] = useState<DocumentItem | null>(null);
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    doc: DocumentItem;
  } | null>(null);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const loadFolders = useCallback(async (parent: string | null) => {
    const { data } = await foldersApi.list({
      parent_id: parent ?? undefined,
    });
    if (data.success && data.data) {
      setFolders(data.data.folders);
      setBreadcrumb(data.data.breadcrumb);
    }
  }, []);

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (favoritesOnly) {
        const { data } = await documentsApi.favorites({
          limit: PAGE_SIZE,
          offset: (page - 1) * PAGE_SIZE,
        });
        if (data.success && data.data) {
          setDocuments(data.data.items);
          setTotal(data.data.total);
        }
      } else {
        const params = {
          folder_id: folderId ?? undefined,
          q: search.trim() || undefined,
          file_type: fileType !== "all" ? fileType : undefined,
          date_preset: datePreset !== "all" ? datePreset : undefined,
          limit: PAGE_SIZE,
          offset: (page - 1) * PAGE_SIZE,
        };
        const { data } = search.trim()
          ? await documentsApi.search({ ...params, q: search.trim() })
          : await documentsApi.list(params);
        if (data.success && data.data) {
          setDocuments(data.data.items);
          setTotal(data.data.total);
        }
      }
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load documents"));
    } finally {
      setLoading(false);
    }
  }, [favoritesOnly, folderId, search, fileType, datePreset, page]);

  useEffect(() => {
    loadFolders(folderId).catch((err) =>
      toast.error(getErrorMessage(err, "Failed to load folders"))
    );
  }, [folderId, loadFolders]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  useEffect(() => {
    const close = () => setContextMenu(null);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, []);

  const navigateFolder = (id: string | null) => {
    setFolderId(id);
    setPage(1);
    setFavoritesOnly(false);
  };

  const handleUpload = async (files: File[]) => {
    if (!files.length) return;
    setUploading(true);
    try {
      for (const file of files) {
        setProgress((p) => ({ ...p, [file.name]: 0 }));
        const { data } = await documentsApi.upload(file, {
          folder_id: folderId,
          onProgress: (pct) =>
            setProgress((p) => ({ ...p, [file.name]: pct })),
        });
        if (data.success) {
          toast.success(
            data.data?.duplicate_detected
              ? `${file.name} uploaded (duplicate content detected)`
              : `${file.name} uploaded`
          );
        }
      }
      setUploadOpen(false);
      setProgress({});
      await loadDocuments();
    } catch (err) {
      toast.error(getErrorMessage(err, "Upload failed"));
    } finally {
      setUploading(false);
    }
  };

  const createFolder = async () => {
    if (!newFolderName.trim()) return;
    try {
      await foldersApi.create({
        name: newFolderName.trim(),
        parent_id: folderId,
      });
      toast.success("Folder created");
      setFolderModal(false);
      setNewFolderName("");
      await loadFolders(folderId);
    } catch (err) {
      toast.error(getErrorMessage(err, "Could not create folder"));
    }
  };

  const deleteFolder = async (folder: FolderItem) => {
    if (!window.confirm(`Delete folder "${folder.name}"?`)) return;
    try {
      await foldersApi.remove(folder.id);
      toast.success("Folder deleted");
      await loadFolders(folderId);
    } catch (err) {
      toast.error(getErrorMessage(err, "Could not delete folder"));
    }
  };

  const rename = async () => {
    if (!renameDoc || !renameValue.trim()) return;
    try {
      await documentsApi.update(renameDoc.id, { filename: renameValue.trim() });
      toast.success("Renamed");
      setRenameDoc(null);
      await loadDocuments();
    } catch (err) {
      toast.error(getErrorMessage(err, "Rename failed"));
    }
  };

  const actions = useMemo(
    () => ({
      preview: (doc: DocumentItem) => setPreviewDoc(doc),
      download: async (doc: DocumentItem) => {
        try {
          await documentsApi.download(doc.id, doc.filename);
        } catch (err) {
          toast.error(getErrorMessage(err, "Download failed"));
        }
      },
      favorite: async (doc: DocumentItem) => {
        try {
          await documentsApi.favorite(doc.id);
          await loadDocuments();
        } catch (err) {
          toast.error(getErrorMessage(err, "Favorite failed"));
        }
      },
      archive: async (doc: DocumentItem) => {
        try {
          await documentsApi.archive(doc.id);
          toast.success("Archived");
          await loadDocuments();
        } catch (err) {
          toast.error(getErrorMessage(err, "Archive failed"));
        }
      },
      remove: async (doc: DocumentItem) => {
        if (!window.confirm(`Delete "${doc.filename}"?`)) return;
        try {
          await documentsApi.remove(doc.id);
          toast.success("Deleted");
          await loadDocuments();
        } catch (err) {
          toast.error(getErrorMessage(err, "Delete failed"));
        }
      },
      rename: (doc: DocumentItem) => {
        setRenameDoc(doc);
        setRenameValue(doc.filename);
      },
    }),
    [loadDocuments]
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold tracking-tight">
            Documents
          </h1>
          <p className="mt-1 text-muted-foreground">
            Enterprise file manager — upload, organize, preview, and search
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant={favoritesOnly ? "default" : "outline"}
            onClick={() => {
              setFavoritesOnly((v) => !v);
              setPage(1);
            }}
          >
            <Star className="h-4 w-4" />
            Favorites
          </Button>
          <Button onClick={() => setUploadOpen(true)}>
            <Upload className="h-4 w-4" />
            Upload
          </Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
        <FolderTree
          folders={folders}
          breadcrumb={breadcrumb}
          currentFolderId={folderId}
          onNavigate={navigateFolder}
          onCreate={() => setFolderModal(true)}
          onDelete={deleteFolder}
          className="min-h-[420px]"
        />

        <div className="space-y-4">
          <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-3 sm:flex-row sm:items-center">
            <SearchBar
              value={search}
              onChange={(v) => {
                setSearch(v);
                setPage(1);
              }}
              placeholder="Search filename, tags, description…"
              className="flex-1"
            />
            <select
              value={fileType}
              onChange={(e) => {
                setFileType(e.target.value);
                setPage(1);
              }}
              className="h-10 rounded-lg border border-input bg-background px-3 text-sm"
            >
              <option value="all">All types</option>
              <option value="pdf">PDF</option>
              <option value="images">Images</option>
              <option value="documents">Documents</option>
            </select>
            <select
              value={datePreset}
              onChange={(e) => {
                setDatePreset(e.target.value);
                setPage(1);
              }}
              className="h-10 rounded-lg border border-input bg-background px-3 text-sm"
            >
              <option value="all">Any time</option>
              <option value="today">Today</option>
              <option value="last_week">Last week</option>
              <option value="last_month">Last month</option>
            </select>
            <div className="flex rounded-lg border border-border p-0.5">
              <Button
                variant={view === "grid" ? "secondary" : "ghost"}
                size="icon"
                className="h-9 w-9"
                onClick={() => setView("grid")}
              >
                <Grid3X3 className="h-4 w-4" />
              </Button>
              <Button
                variant={view === "list" ? "secondary" : "ghost"}
                size="icon"
                className="h-9 w-9"
                onClick={() => setView("list")}
              >
                <LayoutList className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {loading ? (
            <Loader label="Loading documents…" />
          ) : error ? (
            <ErrorState message={error} onRetry={loadDocuments} />
          ) : documents.length === 0 ? (
            <EmptyState
              icon={Upload}
              title="No documents yet"
              description="Upload files or adjust filters to see results."
              actionLabel="Upload files"
              onAction={() => setUploadOpen(true)}
            />
          ) : view === "grid" ? (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    setContextMenu({ x: e.clientX, y: e.clientY, doc });
                  }}
                >
                  <FileCard
                    doc={doc}
                    onPreview={() => actions.preview(doc)}
                    onDownload={() => actions.download(doc)}
                    onFavorite={() => actions.favorite(doc)}
                    onArchive={() => actions.archive(doc)}
                    onDelete={() => actions.remove(doc)}
                    onRename={() => actions.rename(doc)}
                  />
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-border">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/30 hover:bg-muted/30">
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Owner</TableHead>
                    <TableHead>Size</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {documents.map((doc) => (
                    <TableRow
                      key={doc.id}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        setContextMenu({ x: e.clientX, y: e.clientY, doc });
                      }}
                    >
                      <TableCell className="font-medium">
                        {doc.is_favorited ? "★ " : ""}
                        {doc.filename}
                      </TableCell>
                      <TableCell className="uppercase text-muted-foreground">
                        {doc.extension}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {doc.owner_name ?? "—"}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatBytes(doc.size)}
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary">{doc.status}</Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(doc.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="space-x-1 text-right">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => actions.preview(doc)}
                        >
                          Preview
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => actions.download(doc)}
                        >
                          Download
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-destructive"
                          onClick={() => actions.remove(doc)}
                        >
                          Delete
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {!loading && documents.length > 0 ? (
            <Pagination
              page={Math.min(page, totalPages)}
              totalPages={totalPages}
              onPageChange={setPage}
            />
          ) : null}
        </div>
      </div>

      <Modal
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        title="Upload documents"
        description="Multiple files supported. Large uploads show progress."
      >
        <UploadZone onFiles={handleUpload} disabled={uploading} />
        <div className="mt-4 space-y-2">
          {Object.entries(progress).map(([name, pct]) => (
            <ProgressBar key={name} label={name} value={pct} />
          ))}
        </div>
      </Modal>

      <Modal
        open={folderModal}
        onOpenChange={setFolderModal}
        title="New folder"
      >
        <Input
          value={newFolderName}
          onChange={(e) => setNewFolderName(e.target.value)}
          placeholder="Folder name"
          onKeyDown={(e) => e.key === "Enter" && createFolder()}
        />
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setFolderModal(false)}>
            Cancel
          </Button>
          <Button onClick={createFolder}>Create</Button>
        </div>
      </Modal>

      <Modal
        open={!!renameDoc}
        onOpenChange={(o) => !o && setRenameDoc(null)}
        title="Rename document"
      >
        <Input
          value={renameValue}
          onChange={(e) => setRenameValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && rename()}
        />
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setRenameDoc(null)}>
            Cancel
          </Button>
          <Button onClick={rename}>Save</Button>
        </div>
      </Modal>

      <MetadataDrawer
        open={!!previewDoc}
        onOpenChange={(o) => !o && setPreviewDoc(null)}
        document={previewDoc}
      />

      {contextMenu ? (
        <div
          className="fixed z-50 min-w-[160px] rounded-lg border border-border bg-popover py-1 shadow-lg"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          {(
            [
              ["Preview", () => actions.preview(contextMenu.doc)],
              ["Download", () => actions.download(contextMenu.doc)],
              ["Rename", () => actions.rename(contextMenu.doc)],
              ["Favorite", () => actions.favorite(contextMenu.doc)],
              ["Archive", () => actions.archive(contextMenu.doc)],
              ["Delete", () => actions.remove(contextMenu.doc)],
            ] as const
          ).map(([label, fn]) => (
            <button
              key={label}
              type="button"
              className="block w-full px-3 py-2 text-left text-sm hover:bg-accent"
              onClick={() => {
                fn();
                setContextMenu(null);
              }}
            >
              {label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
