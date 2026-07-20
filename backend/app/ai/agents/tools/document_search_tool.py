from __future__ import annotations

from typing import Any

from app.ai.agents.registry import BaseTool, ToolContext, ToolResult, register_tool


@register_tool
class DocumentSearchTool(BaseTool):
    name = "document_search"
    description = "Search DMS documents by filename or keyword."
    tags = ["document", "search"]
    agent_types = ["document", "knowledge", "general_assistant"]
    required_permissions = ["documents:read"]
    input_schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
        "required": ["query"],
    }

    async def execute(self, ctx: ToolContext, **kwargs: Any) -> ToolResult:
        from app.repositories.document_repository import DocumentRepository

        q = str(kwargs.get("query") or "").strip()
        limit = int(kwargs.get("limit") or 20)
        repo = DocumentRepository(ctx.session)
        docs, total = await repo.list_accessible(ctx.user, q=q, limit=limit, offset=0)
        return ToolResult(
            True,
            data={
                "total": total,
                "documents": [
                    {
                        "id": str(d.id),
                        "filename": d.filename,
                        "status": d.status,
                        "extension": d.extension,
                    }
                    for d in docs
                ],
            },
        )


@register_tool
class DocumentSummarizerTool(BaseTool):
    name = "document_summarizer"
    description = "Summarize a document using RAG over that document only."
    tags = ["document", "summarize"]
    agent_types = ["document", "knowledge", "general_assistant"]
    required_permissions = ["documents:read"]
    input_schema = {
        "type": "object",
        "properties": {
            "document_id": {"type": "string"},
            "focus": {"type": "string"},
        },
        "required": ["document_id"],
    }

    async def execute(self, ctx: ToolContext, **kwargs: Any) -> ToolResult:
        from uuid import UUID

        from app.ai.rag.engine import RAGEngine

        doc_id = kwargs.get("document_id")
        if not doc_id:
            return ToolResult(False, error="document_id is required")
        focus = kwargs.get("focus") or "Provide an executive summary of this document."
        rag = RAGEngine(ctx.session)
        result = await rag.answer(
            ctx.user, str(focus), document_id=UUID(str(doc_id))
        )
        return ToolResult(
            True,
            data={
                "summary": result.answer,
                "citations": [c.to_dict() for c in result.citations],
            },
        )
