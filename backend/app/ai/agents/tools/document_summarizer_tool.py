"""Document summarizer re-exports registration from document_search_tool (same module load)."""

# Class lives in document_search_tool.py — imported for discoverability / folder contract.
from app.ai.agents.tools.document_search_tool import DocumentSummarizerTool  # noqa: F401
