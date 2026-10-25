# Intelligence OS

> Enterprise-grade private RAG platform with strict multi-tenant isolation and hybrid search capabilities.

---

## Architecture Overview

```
Intelligence OS/
├── docker-compose.yml        # PostgreSQL 16 (pgvector) & Redis 7 services
├── .env.example              # Root environment template
├── .gitignore                # Git ignore rules
├── backend/
│   ├── alembic/              # Database migration versions & async env.py
│   │   ├── versions/
│   │   │   ├── 0001_initial_multi_tenant_schema.py
│   │   │   └── 0002_add_fts_and_hnsw_indexes.py
│   │   └── env.py
│   ├── alembic.ini           # Alembic configuration
│   ├── run_migrations.py     # Resilient migration runner
│   ├── test_auth_flow.py     # Multi-tenant RBAC & auth verification suite
│   ├── test_ingestion_flow.py# Document parsing, chunking & ingestion test suite
│   ├── test_hybrid_search.py # Vector embeddings, FTS & RRF retrieval test suite
│   ├── app/
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── endpoints/
│   │   │   │   │   ├── auth.py      # Registration, Login (JSON/OAuth2), /auth/me
│   │   │   │   │   ├── documents.py # PDF Upload (202), status, retrieval, deletion
│   │   │   │   │   ├── health.py    # Asynchronous deep healthcheck endpoint
│   │   │   │   │   ├── org.py       # Multi-tenant user & org management
│   │   │   │   │   └── search.py    # Hybrid vector + keyword search with RRF
│   │   │   │   └── api.py           # v1 API Router aggregation
│   │   │   └── deps.py              # Auth, RBAC, tenant isolation & DB dependencies
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic v2 BaseSettings configuration
│   │   │   ├── database.py          # SQLAlchemy AsyncPG engine & session helpers
│   │   │   └── security.py          # Passlib bcrypt & JWT generation/decoding
│   │   ├── models/                  # SQLAlchemy 2.0 ORM models
│   │   │   ├── organization.py      # Organization (tenant root)
│   │   │   ├── user.py              # User (ADMIN / MEMBER roles)
│   │   │   ├── document.py          # Document & DocumentChunk (Vector 1536)
│   │   │   └── conversation.py      # Conversation & Message (JSONB citations/traces)
│   │   ├── schemas/                 # Pydantic request & response models
│   │   │   ├── auth.py              # Token, OrgRegisterRequest, LoginRequest
│   │   │   ├── document.py          # DocumentUploadResponse, DocumentResponse, DocumentDetailResponse
│   │   │   ├── health.py            # HealthResponse
│   │   │   ├── org.py               # OrgResponse, OrgCreate
│   │   │   ├── search.py            # SearchRequest, SearchResponse, SearchResultItemResponse
│   │   │   └── user.py              # UserResponse, UserProfileResponse, UserCreate
│   │   ├── services/                # Core business logic services
│   │   │   ├── chunker.py           # Context-preserving token chunker (tiktoken cl100k_base)
│   │   │   ├── document_service.py  # Ingestion validator & async worker pipeline
│   │   │   ├── embedding_service.py # Vector embeddings (OpenAI + deterministic fallback)
│   │   │   ├── pdf_parser.py        # PDF page extractor & heading detector
│   │   │   └── retrieval_service.py # Parallel vector + keyword hybrid search & RRF
│   │   └── main.py                  # FastAPI application entrypoint & CORS setup
│   ├── requirements.txt             # Backend dependencies
│   ├── .env.example                 # Backend environment template
│   └── .env                         # Local development configuration
└── README.md                        # Project documentation
```

---

## Multi-Tenant Data Isolation & Hybrid Search Architecture

1. **Strict Tenant Scoping (`org_id`)**:
   - Every single entity (`User`, `Document`, `DocumentChunk`, `Conversation`) is bound to an `organizations.id` via foreign keys with `ON DELETE CASCADE`.
   - The FastAPI dependency `get_current_tenant` extracts `org_id` directly from the authenticated JWT token signature, preventing callers from spoofing tenant IDs.
   - Files are physically stored on disk under `{UPLOAD_DIR}/{org_id}/{document_id}.pdf` to prevent path traversal and cross-tenant collision.
   - All retrieval queries (both vector cosine distance and full-text keyword search) strictly enforce `WHERE org_id = :org_id` on every query branch.

2. **Parallel Hybrid Search with Reciprocal Rank Fusion (RRF)**:
   - **Vector Branch**: Generates 1536-dimensional query embeddings and computes cosine distance via pgvector's `<=>` operator (accelerated by an HNSW index with `vector_cosine_ops`).
   - **Full-Text Keyword Branch**: Evaluates lexical relevance using PostgreSQL `to_tsvector('english', content)` and `plainto_tsquery('english', query)` scored with `ts_rank_cd` (accelerated by a GIN index).
   - **RRF Merge**: Combines ranked candidate sets using the reciprocal rank fusion formula:
     $$\text{RRF\_Score}(d) = \frac{w_{\text{vec}}}{\text{RRF\_K} + \text{rank}_{\text{vec}}(d)} + \frac{w_{\text{kw}}}{\text{RRF\_K} + \text{rank}_{\text{kw}}(d)}$$
   - Deduplicates chunks by `chunk_id` and attaches complete citation metadata (`document_title`, `page_number`, `section_heading`, `content`, `score`).

3. **Embedding Service (`embedding_service.py`)**:
   - Integrates with OpenAI's `text-embedding-3-small` API.
   - Features a zero-dependency deterministic feature-hashing mock vector generator when `OPENAI_API_KEY` is not provided, allowing offline testing and CI workflows to run reliably without network or cost overhead.

---

## Infrastructure Services (Docker)

1. **PostgreSQL 16 with pgvector (`pgvector/pgvector:pg16`)**
   - Host Port: `5432`
   - Persistent Volume: `postgres_data`
   - Extensions: `uuid-ossp`, `vector`
   - Indexes: HNSW on `embedding`, GIN on `to_tsvector('english', content)`, composite on `(org_id, document_id)`

2. **Redis 7 Alpine (`redis:7-alpine`)**
   - Host Port: `6379`
   - Persistent Volume: `redis_data`

### Starting Docker Services

```bash
docker compose up -d
```

---

## Backend Setup & Verification

### 1. Environment Setup

```bash
cd backend
python -m venv .venv

# Windows
.\.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Local AI Setup (100% Free & Local, Zero External API Keys)

Intelligence OS runs entirely locally without any external paid API dependencies:

1. **Local Embeddings**: Powered by `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions, L2-normalized). Automatically downloaded and cached via PyTorch / HuggingFace.
2. **Local Cross-Encoder Reranker**: Powered by `cross-encoder/ms-marco-MiniLM-L-6-v2` for precise semantic re-ranking.
3. **Local LLM Generation (Ollama)**:
   - Install Ollama (Native Windows or WSL2):
     ```bash
     curl -fsSL https://ollama.com/install.sh | sh
     ```
   - Pull the ultra-fast, capable 1.3GB model:
     ```bash
     ollama pull llama3.2:1b
     ```
   - Ensure Ollama is listening on `http://localhost:11434` (default). In WSL2, set `OLLAMA_HOST=0.0.0.0:11434`.

### 3. Run Database Migrations

```bash
# Direct alembic CLI
alembic upgrade head

# Or using the resilient connectivity-checking runner:
python run_migrations.py
```

> **Note on Offline Development**: If Docker / PostgreSQL is not running, Intelligence OS automatically falls back to an offline SQLite database (`backend/intelligence_os_dev.db`) with full schema and multi-tenant isolation preserved.

### 4. Run Verification Test Suites & Benchmark

```bash
# Step 2 Verification (Auth, RBAC, Multi-Tenant User Management)
python test_auth_flow.py

# Step 3 Verification (PDF Ingestion, Parsing, Chunking & Background Worker)
python test_ingestion_flow.py

# Step 4 Verification (Vector Embeddings, pgvector, FTS Keyword & RRF Hybrid Search)
python test_hybrid_search.py

# Step 5 Verification (Query Rewriting, Cross-Encoder Reranking, Grounded RAG & Citations)
python test_rag_pipeline.py

# Step 6 Verification (Frontend/Backend End-to-End Contract & Guardrail Verification)
python test_frontend_e2e_contract.py

# RAG Retrieval & Sufficiency Benchmark (50 evaluation test cases)
python test_eval_runner.py
```

### 5. Running the Complete System (Backend + Frontend)

To launch both the FastAPI backend and Next.js frontend concurrently:

```powershell
# PowerShell
.\run_dev.ps1

# Or Windows Command Prompt
run_dev.bat
```

Or run independently:

```bash
# Terminal 1: Backend
cd backend
.\.venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

- **Frontend Application**: [http://localhost:3000](http://localhost:3000)
- **Document Admin Console**: [http://localhost:3000/documents](http://localhost:3000/documents)
- **FastAPI Backend**: [http://localhost:8000](http://localhost:8000)
- **API Documentation (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 6. Authentication & Local Testing Credentials

For local development and testing, you can use either:
- **Pre-configured User with Northstar Document**:
  - Email: `sp23-bcs-151@cuilahore.edu.pk`
  - Password: `Admin123!`
  - Includes pre-ingested `Zeploy_Client_Project_Brief_Intelligence_OS_Test.pdf`
- **Demo Administrator**:
  - Email: `admin@demo.com`
  - Password: `Admin123!`
- **Self-Registration**:
  - Visit [http://localhost:3000/register](http://localhost:3000/register) to create any new isolated tenant organization and admin account.
