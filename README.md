# Intelligence OS

> Multi-tenant RAG platform with hybrid retrieval, grounded answers with citations, and an evaluation framework gated in CI.

---

## Overview

Intelligence OS is an enterprise document intelligence and retrieval-augmented generation (RAG) platform. It provides strict multi-tenant isolation, hybrid vector and lexical search, context-aware query rewriting, cross-encoder reranking, and grounded answers with source citations. The platform includes an automated evaluation framework with deterministic CI regression gating.

---

## Architecture & Stack

### Core Components

- **Backend**: FastAPI (Python 3.11+) asynchronous REST API.
- **Primary Database & Vector Store**: PostgreSQL 16 with `pgvector` extension for 1536-dimensional vector similarity search.
- **Cache & Message Broker**: Redis 7 for session caching and transient state.
- **Frontend**: Next.js 16 (React 19, TypeScript, Tailwind CSS) document workspace and conversational interface located in `/frontend`.
- **Database Migrations**: Alembic for asynchronous schema migrations.

### API Endpoints (`backend/app/api/v1/endpoints/`)

| Router | Base Path | Description |
| :--- | :--- | :--- |
| **Auth** | `/api/v1/auth` | User registration, JSON/OAuth2 password authentication, `/auth/me` identity endpoint. |
| **Org** | `/api/v1/org` | Multi-tenant organization profile, member management, and role-based access control. |
| **Documents** | `/api/v1/documents` | Multipart PDF upload (HTTP 202 Accepted), ingestion status polling, document retrieval, and cascading deletion. |
| **Search** | `/api/v1/search` | Hybrid vector + full-text search with Reciprocal Rank Fusion (RRF). |
| **Chat** | `/api/v1/chat` | Conversational RAG with query rewriting, grounded multi-turn response generation, and citation attribution. |
| **Evaluations** | `/api/v1/evaluations` | Benchmark dataset management, async evaluation runs, cancellation, crash recovery, and regression gate checks. |
| **Health** | `/api/v1/health` | Deep asynchronous health check validating PostgreSQL, pgvector extension, and Redis connectivity. |

---

## Retrieval Pipeline

The retrieval pipeline guarantees strict tenant boundaries and retrieves high-precision context:

1. **Tenant Isolation**:
   - `org_id` is extracted directly from the verified JWT token claims by `get_current_tenant`.
   - Every database model (`User`, `Document`, `DocumentChunk`, `Conversation`, `EvaluationRun`) enforces foreign-key scoping to `organizations.id`.
   - All retrieval queries strictly apply `WHERE org_id = :org_id` across vector, keyword, and conversation branches.
   - Files are partitioned on disk by tenant under `uploads/{org_id}/{document_id}.pdf`.

2. **Parallel Hybrid Search**:
   - **Vector Search**: Generates 1536-dimensional query embeddings and computes cosine distance (`<=>`) backed by a PostgreSQL `HNSW` index (`vector_cosine_ops`).
   - **Full-Text Keyword Search**: Generates English text vectors via `to_tsvector('english', content)` and evaluates queries via `plainto_tsquery('english', query)` scored with `ts_rank_cd`, backed by a `GIN` index.

3. **Reciprocal Rank Fusion (RRF)**:
   - Fuses ranked candidate lists using reciprocal rank scores:
     $$\text{RRF\_Score}(d) = \frac{w_{\text{vec}}}{k + \text{rank}_{\text{vec}}(d)} + \frac{w_{\text{kw}}}{k + \text{rank}_{\text{kw}}(d)}$$
   - Default parameters: $k = 60$, $w_{\text{vec}} = 0.5$, $w_{\text{kw}} = 0.5$.

4. **Query Rewriting & Cross-Encoder Reranking**:
   - Conversational follow-ups are rewritten into standalone search queries based on prior turns.
   - Retrieved candidate chunks are reranked using cross-encoders to ensure top-rank relevance before synthesis.

5. **Grounded Answers with Citations**:
   - Synthesizer prompts enforce page-level citation anchors `[DocTitle, p. X]`.
   - Responses lacking document grounding or attempting out-of-scope answers trigger explicit refusals.

---

## Evaluation Framework

For detailed architecture, configuration, and thresholds, see the [Evaluation Framework Documentation](backend/app/eval/README.md).

- **50-Case Golden Benchmark**: Standardized benchmark covering single-hop, multi-hop, coreference resolution, semantic search, retrieval edge cases, citation sensitivity, and unanswerable/adversarial queries.
- **Dual Judge Modes**:
  - **Deterministic CI Judge** (`--judge deterministic --offline`): Fast, fully offline lexical and mathematical scoring (Recall@k, MRR, nDCG@5, Citation Precision/Coverage, Refusal Rates) with zero external API dependencies.
  - **LLM Judge** (`--judge llm`): Semantic evaluation measuring Faithfulness, Correctness, and Completeness using Gemini or OpenAI.
- **Asynchronous Execution & Recovery**: Long-running evaluation jobs run as background tasks with polling status, graceful cancellation support, and crash recovery.
- **CI Regression Gate**: Integrated into `.github/workflows/rag-evaluation.yml`. Automatically halts PRs and pushes if metrics fall below regression thresholds.

### Benchmark Results

The following results were measured running the deterministic offline benchmark:

```bash
python -m app.eval.cli --judge deterministic --offline --check-regression --db-url sqlite+aiosqlite:///ci_eval.db --output-json eval-results.json
```

| Metric | Target Threshold | Actual Result | Status |
| :--- | :---: | :---: | :---: |
| **Total Test Cases** | 50 | 50 | COMPLETE |
| **Passed Test Cases** | >= 45 | 48 | PASS |
| **Overall Pass Rate** | >= 90.0% | 96.0% | PASS |
| **Recall@3** | >= 0.8500 | 0.9111 | PASS |
| **Recall@5** | >= 0.9000 | 0.9667 | PASS |
| **Mean Reciprocal Rank (MRR)** | >= 0.8000 | 0.8458 | PASS |
| **nDCG@5** | >= 0.8500 | 0.8662 | PASS |
| **Citation Precision** | >= 0.8500 | 1.0000 | PASS |
| **Citation Coverage** | >= 0.9000 | 1.0000 | PASS |
| **Correct Refusal Rate (CRR)** | == 1.0000 | 1.0000 | PASS |
| **False Refusal Rate (FRR)** | <= 0.0500 | 0.0000 | PASS |
| **Mean Latency** | <= 350.0 ms | 15.74 ms | PASS |
| **P95 Latency** | <= 600.0 ms | 20.32 ms | PASS |
| **CI Regression Gate** | 11 / 11 checks | 11 / 11 checks | PASSED |

*Note: Offline deterministic mode with mock embeddings; not a measure of live-model quality.*

---

## Project Structure

```
intelligence-os/
├── docker-compose.yml           # PostgreSQL 16 (pgvector) & Redis 7 services
├── .env.example                 # Root environment template
├── .github/
│   └── workflows/
│       └── rag-evaluation.yml   # CI deterministic evaluation regression gate
├── backend/
│   ├── .env.example             # Backend environment template
│   ├── alembic/                 # Asynchronous schema migrations
│   │   └── versions/
│   ├── app/
│   │   ├── api/v1/endpoints/    # auth, org, documents, search, chat, evaluations, health
│   │   ├── core/                # config, database, security
│   │   ├── eval/                # Evaluation benchmark, CLI, runner, judges, metrics
│   │   ├── models/              # SQLAlchemy ORM models (tenant-scoped)
│   │   ├── schemas/             # Pydantic request and response schemas
│   │   ├── services/            # chunker, document_service, embedding, pdf_parser, retrieval
│   │   └── main.py              # FastAPI app and middleware
│   ├── requirements.txt         # Backend Python dependencies
│   ├── run_migrations.py        # Database migration runner
│   └── test_*.py                # Component and integration test suites
├── frontend/
│   ├── app/                     # Next.js App Router (chat, documents, evaluations)
│   ├── components/              # UI components and navigation
│   ├── package.json             # Frontend dependencies
│   └── tests/                   # Contract and UI tests
├── run_dev.ps1                  # Development startup script (PowerShell)
├── run_dev.bat                  # Development startup script (CMD)
└── README.md
```

---

## Getting Started

### 1. Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Node.js 18+ and npm

### 2. Start Infrastructure

```bash
docker compose up -d
```

This starts:
- PostgreSQL 16 with pgvector on port `5432`
- Redis 7 on port `6379`

### 3. Backend Setup

```bash
cd backend
python -m venv .venv

# Windows
.\.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Run database migrations:

```bash
python run_migrations.py
# Or directly via alembic:
alembic upgrade head
```

Start the FastAPI backend:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### 4. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

- Web Interface: [http://localhost:3000](http://localhost:3000)

Alternatively, launch both services together using the root helper:

```powershell
.\run_dev.ps1
```

---

## Test Suites

All test suites can be executed inside the `backend` directory with the virtual environment activated:

```bash
cd backend

# Authentication, RBAC, and multi-tenant scoping
python test_auth_flow.py

# PDF parsing, token chunking, and ingestion pipeline
python test_ingestion_flow.py

# Vector embeddings, pgvector HNSW, and FTS keyword search
python test_hybrid_search.py

# Query rewriting, reranking, and citation generation
python test_rag_pipeline.py

# Frontend-to-backend API contract verification
python test_frontend_e2e_contract.py

# Evaluation metrics and regression calculation tests
python test_eval_metrics.py
python test_eval_regression.py

# Evaluation runner and background cancellation/recovery
python test_eval_runner.py
python test_eval_cancellation_recovery.py

# Evaluation dataset and run API endpoints
python test_eval_datasets.py
python test_eval_api.py
```
