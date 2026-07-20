from __future__ import annotations

from typing import Any

from app.ai.agents.registry import BaseTool, ToolContext, ToolResult, register_tool


@register_tool
class RAGSearchTool(BaseTool):
    name = "rag_search"
    description = "Search the company knowledge base with RAG and return a grounded answer with citations."
    tags = ["knowledge", "rag", "search"]
    agent_types = ["knowledge", "document", "general_assistant"]
    required_permissions = ["documents:read"]
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "User question"},
            "document_id": {"type": "string", "description": "Optional document UUID filter"},
        },
        "required": ["query"],
    }

    async def execute(self, ctx: ToolContext, **kwargs: Any) -> ToolResult:
        from uuid import UUID

        from app.ai.rag.engine import RAGEngine

        query = str(kwargs.get("query") or "").strip()
        if not query:
            return ToolResult(False, error="query is required")
        document_id = kwargs.get("document_id")
        doc_uuid = UUID(str(document_id)) if document_id else None
        rag = RAGEngine(ctx.session)
        result = await rag.answer(ctx.user, query, document_id=doc_uuid)
        return ToolResult(
            True,
            data={
                "answer": result.answer,
                "citations": [c.to_dict() for c in result.citations],
                "grounded": result.grounded,
                "metrics": result.metrics,
            },
        )


@register_tool
class KnowledgeSearchTool(BaseTool):
    name = "knowledge_search"
    description = "Semantic knowledge search across indexed documents (retrieve snippets only)."
    tags = ["knowledge", "search"]
    agent_types = ["knowledge", "general_assistant"]
    required_permissions = ["documents:read"]
    input_schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}, "top_k": {"type": "integer"}},
        "required": ["query"],
    }

    async def execute(self, ctx: ToolContext, **kwargs: Any) -> ToolResult:
        from app.ai.rag.engine import RAGEngine

        query = str(kwargs.get("query") or "").strip()
        if not query:
            return ToolResult(False, error="query is required")
        top_k = int(kwargs.get("top_k") or 5)
        rag = RAGEngine(ctx.session)
        citations, metrics = await rag.retrieve(ctx.user, query, top_k=top_k)
        return ToolResult(
            True,
            data={
                "results": [c.to_dict() for c in citations],
                "metrics": metrics,
            },
        )
