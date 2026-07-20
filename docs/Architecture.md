# Architecture

## Production architecture

```mermaid
flowchart TB
  Dev[Developer] --> GH[GitHub]
  GH --> GHA[GitHub Actions]
  GHA --> Build[Docker Build]
  Build --> Reg[Container Registry]
  Reg --> K8s[Kubernetes]
  K8s --> Ing[Ingress / Nginx]
  Ing --> FE[Frontend]
  Ing --> BE[Backend API]
  BE --> PG[(PostgreSQL)]
  BE --> MG[(MongoDB)]
  BE --> RD[(Redis)]
  BE --> QD[(Qdrant)]
  BE --> WK[Workers]
  K8s --> Mon[Prometheus]
  Mon --> Grf[Grafana]
  BE --> Logs[JSON Logs]
```

## Logical application layers

```mermaid
flowchart LR
  UI[React SPA] --> API[FastAPI /api/v1]
  API --> Auth[Auth / RBAC / Tenancy]
  API --> DMS[Documents]
  API --> RAG[Chat / RAG]
  API --> OCR[OCR / Vision]
  API --> Meet[Meetings]
  API --> Agt[Agents]
  API --> An[Analytics]
  API --> Adm[Admin SaaS]
  Auth --> PG[(Postgres)]
  DMS --> Obj[Object Storage]
  RAG --> QD[(Qdrant)]
  API --> RD[(Redis)]
  An --> MG[(Mongo)]
```

## Authentication flow

```mermaid
sequenceDiagram
  participant U as User
  participant FE as Frontend
  participant API as Backend
  participant DB as Postgres
  U->>FE: Login
  FE->>API: POST /auth/login
  API->>DB: Verify user + tenant
  API-->>FE: access JWT + refresh
  Note over FE,API: JWT claims: sub, roles, tenant_id, organization_id, team_id
  FE->>API: API calls + Bearer token
  API->>API: TenantContext + RBAC
```

## RAG pipeline

```mermaid
flowchart TD
  Upload[Document upload] --> Parse[Parse / chunk]
  Parse --> Embed[Embeddings]
  Embed --> Qdrant[(Qdrant)]
  Q[User question] --> Retrieve[Vector retrieve]
  Qdrant --> Retrieve
  Retrieve --> Prompt[Grounded prompt]
  Prompt --> LLM[LLM]
  LLM --> Answer[Cited answer]
```

## OCR pipeline

```mermaid
flowchart LR
  Img[Image / PDF] --> Job[OCR Job]
  Job --> Eng[OCR Engine]
  Eng --> Text[Extracted text]
  Text --> Store[(Postgres)]
  Text --> Index[Optional RAG index]
```

## Meeting pipeline

```mermaid
flowchart TD
  Audio[Audio upload] --> AQ[Audio queue]
  AQ --> TR[Transcription]
  TR --> DI[Diarization]
  DI --> SU[Summary / actions]
  SU --> EM[Embeddings]
  EM --> QD[(Qdrant)]
```

## Agent pipeline

```mermaid
flowchart TD
  User[User goal] --> Session[Agent session]
  Session --> Plan[Planner]
  Plan --> Tools[Tool registry]
  Tools --> Exec[Executors]
  Exec --> Mem[Memory]
  Exec --> Result[Task result]
```

## Deployment architecture

```mermaid
flowchart TB
  subgraph Edge
    NGX[Nginx / Ingress]
  end
  subgraph App
    FE[Frontend pods]
    BE[Backend pods + HPA]
    WK[Worker pods]
  end
  subgraph Data
    PG[(Postgres PVC)]
    MG[(Mongo PVC)]
    RD[(Redis PVC)]
    QD[(Qdrant PVC)]
  end
  subgraph Observability
    PROM[Prometheus]
    GRAF[Grafana]
  end
  NGX --> FE
  NGX --> BE
  BE --> PG & MG & RD & QD
  BE --> PROM
  PROM --> GRAF
```

## Multi-tenancy

`Tenant → Organization → Team → User → Permissions → Resources`

Every admin and data path is scoped by `tenant_id`. JWT carries tenant claims; `TenantContextMiddleware` enforces request scope.
