# Module 6 — Enterprise RAG Knowledge Assistant

Answers **only** from uploaded company documents, with citations.

## Architecture

```
Upload → Extract → Chunk → Embed → Qdrant
                                      ↓
User question → Retrieve (RBAC filters) → LLM Provider → Answer + Citations
```

## LLM provider switch

```env
LLM_PROVIDER=gemini   # openai | gemini | ollama | azure_openai | anthropic | mock
GEMINI_API_KEY=...
```

```
LLMProvider
├── OpenAIProvider
├── GeminiProvider
├── OllamaProvider
├── AzureOpenAIProvider
├── AnthropicProvider
└── MockLLMProvider
```

## Embeddings

```env
EMBEDDING_PROVIDER=bge   # bge | minilm | mock
# Primary: BAAI/bge-large-en-v1.5  Fallback: all-MiniLM-L6-v2
```

Install heavy models: `pip install -r requirements-ai.txt`

## Key APIs

| Method | Path |
|--------|------|
| POST | `/api/v1/chat` |
| POST | `/api/v1/chat/stream` (SSE) |
| GET | `/api/v1/chat/history` |
| GET/PATCH/DELETE | `/api/v1/chat/{id}` |
| POST | `/api/v1/documents/{id}/index?sync=true` |
| POST | `/api/v1/documents/reindex` |
| GET | `/api/v1/search?q=` |

## Migration

`alembic upgrade head` → `0005_chat_rag`
