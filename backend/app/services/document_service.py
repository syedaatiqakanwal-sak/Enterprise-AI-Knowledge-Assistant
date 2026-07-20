"""Document business logic for Module 5 DMS (no RAG / embeddings / LLM)."""

from __future__ import annotations

import logging
import uuid
from pathlib import PurePosixPath

from fastapi import UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.document import Document, DocumentVersion
from app.models.enums import DocumentStatus, DocumentVisibility
from app.models.user import User
from app.repositories.document_repository import DocumentRepository
from app.repositories.folder_repository import FolderRepository
from app.schemas.document import (
    CopyMoveRequest,
    DocumentListOut,
    DocumentOut,
    DocumentUpdate,
    DocumentUploadResult,
    DocumentVersionOut,
    PreviewOut,
)
from app.services.checksum_service import ChecksumService
from app.services.metadata_service import (
    sanitize_filename,
    unique_storage_key,
    validate_upload,
    virus_scan_placeholder,
)
from app.services.preview_service import PreviewService
from app.services.storage_service import StorageBackend, get_storage_backend
from app.utils.sanitize import sanitize_text

logger = logging.getLogger(__name__)


class DocumentService:
    def __init__(
        self,
        session: AsyncSession,
        storage: StorageBackend | None = None,
    ) -> None:
        self._session = session
        self._docs = DocumentRepository(session)
        self._folders = FolderRepository(session)
        self._storage = storage or get_storage_backend()
        self._preview = PreviewService(self._storage)

    def _is_admin(self, user: User) -> bool:
        return any(r.name == "admin" for r in (user.roles or []))

    def _can_write(self, user: User) -> bool:
        if self._is_admin(user):
            return True
        codes = {
            p.code
            for r in (user.roles or [])
            for p in (r.permissions or [])
        }
        return "documents:write" in codes or "admin:all" in codes

    def _can_delete_any(self, user: User) -> bool:
        if self._is_admin(user):
            return True
        codes = {
            p.code
            for r in (user.roles or [])
            for p in (r.permissions or [])
        }
        return "documents:delete" in codes or "admin:all" in codes

    async def _ensure_access(self, user: User, document: Document) -> None:
        if document.owner_id == user.id:
            return
        if document.visibility == DocumentVisibility.PUBLIC.value:
            return
        if document.visibility == DocumentVisibility.COMPANY.value:
            return
        if (
            document.visibility == DocumentVisibility.ADMIN_ONLY.value
            and self._is_admin(user)
        ):
            return
        raise AppException(
            "You do not have access to this document",
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    async def _ensure_owner_or_admin(self, user: User, document: Document) -> None:
        if document.owner_id == user.id or self._is_admin(user):
            return
        raise AppException(
            "Only the owner or an admin can modify this document",
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    async def _to_out(
        self, document: Document, user: User, *, duplicate_of: uuid.UUID | None = None
    ) -> DocumentOut:
        favorited = await self._docs.is_favorited(user.id, document.id)
        versions = [
            DocumentVersionOut.model_validate(v) for v in (document.versions or [])
        ]
        return DocumentOut(
            id=document.id,
            uuid=document.uuid,
            owner_id=document.owner_id,
            owner_name=document.owner.full_name if document.owner else None,
            company_id=document.company_id,
            folder_id=document.folder_id,
            filename=document.filename,
            original_filename=document.original_filename,
            extension=document.extension,
            mime_type=document.mime_type,
            size=document.size,
            storage_path=document.storage_path,
            thumbnail_path=document.thumbnail_path,
            status=document.status,
            visibility=document.visibility,
            version=document.version,
            checksum=document.checksum,
            tags=list(document.tags or []),
            description=document.description,
            is_favorited=favorited,
            duplicate_of=duplicate_of,
            created_at=document.created_at,
            updated_at=document.updated_at,
            deleted_at=document.deleted_at,
            versions=versions,
        )

    async def _unique_filename(
        self,
        owner_id: uuid.UUID,
        filename: str,
        folder_id: uuid.UUID | None,
    ) -> str:
        if not await self._docs.filename_exists(owner_id, filename, folder_id=folder_id):
            return filename
        stem = PurePosixPath(filename).stem
        suffix = PurePosixPath(filename).suffix
        for i in range(1, 1000):
            candidate = f"{stem} ({i}){suffix}"
            if not await self._docs.filename_exists(
                owner_id, candidate, folder_id=folder_id
            ):
                return candidate
        return f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"

    async def upload(
        self,
        user: User,
        file: UploadFile,
        *,
        folder_id: uuid.UUID | None = None,
        visibility: str = DocumentVisibility.PRIVATE.value,
        description: str | None = None,
        tags: list[str] | None = None,
        # Chunk-upload ready placeholders (ignored for single-shot uploads)
        upload_id: str | None = None,
        chunk_index: int | None = None,
        chunk_total: int | None = None,
    ) -> DocumentUploadResult:
        _ = (upload_id, chunk_index, chunk_total)  # reserved for future chunked uploads
        if not self._can_write(user):
            raise AppException(
                "Missing documents:write permission",
                code="FORBIDDEN",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        if folder_id is not None:
            folder = await self._folders.get_by_id(folder_id)
            if folder is None or folder.owner_id != user.id:
                raise AppException(
                    "Folder not found",
                    code="FOLDER_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

        raw = await file.read()
        safe_name, extension, mime = validate_upload(
            filename=file.filename or "upload.bin",
            content_type=file.content_type,
            size=len(raw),
        )
        if not virus_scan_placeholder(raw):
            raise AppException(
                "File failed virus scan",
                code="VIRUS_DETECTED",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        checksum = ChecksumService.sha256_bytes(raw)
        duplicate = await self._docs.find_by_checksum(user.id, checksum)
        duplicate_of = duplicate.id if duplicate else None

        try:
            visibility_enum = DocumentVisibility(visibility)
        except ValueError as exc:
            raise AppException(
                "Invalid visibility",
                code="INVALID_VISIBILITY",
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from exc

        filename = await self._unique_filename(user.id, safe_name, folder_id)
        storage_key = unique_storage_key(user.id, extension)

        doc_id = uuid.uuid4()
        document = await self._docs.create(
            id=doc_id,
            uuid=doc_id,
            owner_id=user.id,
            folder_id=folder_id,
            filename=filename,
            original_filename=safe_name,
            extension=extension,
            mime_type=mime,
            size=len(raw),
            storage_path=storage_key,
            status=DocumentStatus.UPLOADING.value,
            visibility=visibility_enum.value,
            version=1,
            tags=[sanitize_text(t, max_length=64).lower() for t in (tags or []) if t],
            description=(
                sanitize_text(description, max_length=5000) if description else None
            ),
        )

        try:
            document.status = DocumentStatus.PROCESSING.value
            await self._session.flush()

            await self._storage.save(storage_key, raw)
            # Thumbnail placeholder path (generated by a later media pipeline)
            thumbnail_path = None
            if extension in {"png", "jpg", "jpeg", "webp"}:
                thumbnail_path = storage_key

            document.checksum = checksum
            document.thumbnail_path = thumbnail_path
            document.status = DocumentStatus.READY.value

            await self._docs.add_version(
                DocumentVersion(
                    document_id=document.id,
                    version=1,
                    storage_path=storage_key,
                    size=len(raw),
                    checksum=checksum,
                    mime_type=mime,
                    created_by=user.id,
                )
            )
            await self._session.flush()
        except Exception:
            logger.exception("Upload processing failed for %s", document.id)
            document.status = DocumentStatus.FAILED.value
            await self._session.flush()
            raise AppException(
                "Failed to process uploaded file",
                code="UPLOAD_FAILED",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Reload with relationships
        reloaded = await self._docs.get_by_id(document.id)
        assert reloaded is not None
        out = await self._to_out(reloaded, user, duplicate_of=duplicate_of)
        return DocumentUploadResult(
            document=out,
            duplicate_detected=duplicate_of is not None,
            message=(
                "Upload complete — duplicate content detected"
                if duplicate_of
                else "Upload complete"
            ),
        )

    async def list_documents(
        self,
        user: User,
        *,
        folder_id: uuid.UUID | None = None,
        status_filter: str | None = None,
        extension: str | None = None,
        file_type: str | None = None,
        visibility: str | None = None,
        tag: str | None = None,
        owner_id: uuid.UUID | None = None,
        q: str | None = None,
        date_preset: str | None = None,
        min_size: int | None = None,
        max_size: int | None = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> DocumentListOut:
        date_from, date_to = DocumentRepository.date_range_preset(date_preset)
        ext = extension
        if file_type:
            ft = file_type.lower()
            if ft == "pdf":
                ext = "pdf"
            elif ft == "images":
                # handled via multi-filter below — use first image type loosely
                pass
            elif ft == "documents":
                pass

        items, total = await self._docs.list_accessible(
            user,
            folder_id=folder_id,
            status=status_filter,
            extension=ext,
            visibility=visibility,
            tag=tag,
            owner_id=owner_id,
            q=q,
            date_from=date_from,
            date_to=date_to,
            min_size=min_size,
            max_size=max_size,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )

        # Post-filter image / documents groups
        if file_type:
            ft = file_type.lower()
            if ft == "images":
                items = [d for d in items if d.extension in {"png", "jpg", "jpeg", "webp"}]
                total = len(items)
            elif ft == "documents":
                items = [
                    d
                    for d in items
                    if d.extension in {"pdf", "docx", "txt", "csv", "xlsx", "pptx"}
                ]
                total = len(items)

        outs = [await self._to_out(d, user) for d in items]
        return DocumentListOut(items=outs, total=total, limit=limit, offset=offset)

    async def get(self, user: User, document_id: uuid.UUID) -> DocumentOut:
        document = await self._docs.get_by_id(document_id, include_deleted=True)
        if document is None:
            raise AppException(
                "Document not found",
                code="DOCUMENT_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        await self._ensure_access(user, document)
        return await self._to_out(document, user)

    async def update(
        self, user: User, document_id: uuid.UUID, payload: DocumentUpdate
    ) -> DocumentOut:
        document = await self._docs.get_by_id(document_id)
        if document is None:
            raise AppException(
                "Document not found",
                code="DOCUMENT_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        await self._ensure_owner_or_admin(user, document)

        if payload.filename is not None:
            new_name = sanitize_filename(payload.filename)
            if PurePosixPath(new_name).suffix.lower().lstrip(".") != document.extension:
                # Keep original extension
                new_name = f"{PurePosixPath(new_name).stem}.{document.extension}"
            new_name = await self._unique_filename(
                document.owner_id, new_name, document.folder_id
            )
            document.filename = new_name

        if payload.description is not None:
            document.description = sanitize_text(payload.description, max_length=5000)

        if payload.visibility is not None:
            try:
                document.visibility = DocumentVisibility(payload.visibility).value
            except ValueError as exc:
                raise AppException(
                    "Invalid visibility",
                    code="INVALID_VISIBILITY",
                    status_code=status.HTTP_400_BAD_REQUEST,
                ) from exc

        if payload.move_to_root:
            document.folder_id = None
        elif payload.folder_id is not None:
            folder = await self._folders.get_by_id(payload.folder_id)
            if folder is None or folder.owner_id != user.id:
                raise AppException(
                    "Folder not found",
                    code="FOLDER_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            document.folder_id = payload.folder_id

        if payload.tags is not None:
            document.tags = [
                sanitize_text(t, max_length=64).lower() for t in payload.tags if t
            ]

        await self._session.flush()
        reloaded = await self._docs.get_by_id(document.id)
        assert reloaded is not None
        return await self._to_out(reloaded, user)

    async def soft_delete(self, user: User, document_id: uuid.UUID) -> None:
        document = await self._docs.get_by_id(document_id)
        if document is None:
            raise AppException(
                "Document not found",
                code="DOCUMENT_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if document.owner_id != user.id and not self._can_delete_any(user):
            raise AppException(
                "You cannot delete this document",
                code="FORBIDDEN",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        await self._docs.soft_delete(document)
        try:
            from app.ai.qdrant import get_qdrant_service

            get_qdrant_service().delete_document(str(document.id))
        except Exception:
            logger.debug("Embedding cleanup skipped", exc_info=True)

    async def restore(self, user: User, document_id: uuid.UUID) -> DocumentOut:
        document = await self._docs.get_by_id(document_id, include_deleted=True)
        if document is None:
            raise AppException(
                "Document not found",
                code="DOCUMENT_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        await self._ensure_owner_or_admin(user, document)
        await self._docs.restore(document)
        reloaded = await self._docs.get_by_id(document.id)
        assert reloaded is not None
        return await self._to_out(reloaded, user)

    async def archive(self, user: User, document_id: uuid.UUID) -> DocumentOut:
        document = await self._docs.get_by_id(document_id)
        if document is None:
            raise AppException(
                "Document not found",
                code="DOCUMENT_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        await self._ensure_owner_or_admin(user, document)
        await self._docs.archive(document)
        reloaded = await self._docs.get_by_id(document.id)
        assert reloaded is not None
        return await self._to_out(reloaded, user)

    async def toggle_favorite(self, user: User, document_id: uuid.UUID) -> DocumentOut:
        document = await self._docs.get_by_id(document_id)
        if document is None:
            raise AppException(
                "Document not found",
                code="DOCUMENT_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        await self._ensure_access(user, document)
        if await self._docs.is_favorited(user.id, document.id):
            await self._docs.remove_favorite(user.id, document.id)
        else:
            await self._docs.add_favorite(user.id, document.id)
        return await self._to_out(document, user)

    async def recent(self, user: User, *, limit: int = 20) -> DocumentListOut:
        items = await self._docs.list_recent(user, limit=limit)
        outs = [await self._to_out(d, user) for d in items]
        return DocumentListOut(items=outs, total=len(outs), limit=limit, offset=0)

    async def favorites(
        self, user: User, *, limit: int = 50, offset: int = 0
    ) -> DocumentListOut:
        items, total = await self._docs.list_favorites(
            user.id, limit=limit, offset=offset
        )
        outs = [await self._to_out(d, user) for d in items]
        return DocumentListOut(items=outs, total=total, limit=limit, offset=offset)

    async def search(
        self,
        user: User,
        *,
        q: str,
        limit: int = 50,
        offset: int = 0,
        **filters,
    ) -> DocumentListOut:
        return await self.list_documents(
            user, q=q, limit=limit, offset=offset, **filters
        )

    async def preview(self, user: User, document_id: uuid.UUID) -> PreviewOut:
        document = await self._docs.get_by_id(document_id)
        if document is None:
            raise AppException(
                "Document not found",
                code="DOCUMENT_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        await self._ensure_access(user, document)
        data = await self._preview.build_preview(document)
        return PreviewOut(preview=data)

    async def download_bytes(
        self, user: User, document_id: uuid.UUID
    ) -> tuple[Document, bytes]:
        document = await self._docs.get_by_id(document_id)
        if document is None:
            raise AppException(
                "Document not found",
                code="DOCUMENT_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        await self._ensure_access(user, document)
        data = await self._storage.open(document.storage_path)
        if document.checksum and not ChecksumService.verify(data, document.checksum):
            raise AppException(
                "Checksum validation failed",
                code="CHECKSUM_MISMATCH",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return document, data

    async def copy(
        self, user: User, document_id: uuid.UUID, payload: CopyMoveRequest
    ) -> DocumentOut:
        document = await self._docs.get_by_id(document_id)
        if document is None:
            raise AppException(
                "Document not found",
                code="DOCUMENT_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        await self._ensure_access(user, document)
        if not self._can_write(user):
            raise AppException(
                "Missing documents:write permission",
                code="FORBIDDEN",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        folder_id = None if payload.move_to_root else payload.folder_id
        if folder_id is not None:
            folder = await self._folders.get_by_id(folder_id)
            if folder is None or folder.owner_id != user.id:
                raise AppException(
                    "Folder not found",
                    code="FOLDER_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

        data = await self._storage.open(document.storage_path)
        new_key = unique_storage_key(user.id, document.extension)
        await self._storage.save(new_key, data)
        filename = await self._unique_filename(
            user.id, f"Copy of {document.filename}", folder_id
        )
        new_id = uuid.uuid4()
        copy_doc = await self._docs.create(
            id=new_id,
            uuid=new_id,
            owner_id=user.id,
            folder_id=folder_id,
            filename=filename,
            original_filename=document.original_filename,
            extension=document.extension,
            mime_type=document.mime_type,
            size=document.size,
            storage_path=new_key,
            thumbnail_path=document.thumbnail_path,
            status=DocumentStatus.READY.value,
            visibility=document.visibility,
            version=1,
            checksum=document.checksum,
            tags=list(document.tags or []),
            description=document.description,
        )
        await self._docs.add_version(
            DocumentVersion(
                document_id=copy_doc.id,
                version=1,
                storage_path=new_key,
                size=copy_doc.size,
                checksum=copy_doc.checksum,
                mime_type=copy_doc.mime_type,
                created_by=user.id,
            )
        )
        reloaded = await self._docs.get_by_id(copy_doc.id)
        assert reloaded is not None
        return await self._to_out(reloaded, user)

    async def move(
        self, user: User, document_id: uuid.UUID, payload: CopyMoveRequest
    ) -> DocumentOut:
        update = DocumentUpdate(
            folder_id=payload.folder_id,
            move_to_root=payload.move_to_root,
        )
        return await self.update(user, document_id, update)
