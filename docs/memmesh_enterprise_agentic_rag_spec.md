# MemMesh: Enterprise Agentic RAG Platform (V2)
## Complete Specification & Implementation Architecture

**Version:** 2.0  
**Date:** June 7, 2026  
**Status:** Approved for Core Re-Scaffolding  

---

## 1. System Vision & Objectives

MemMesh is a multi-tenant, agentic Retrieval-Augmented Generation (RAG) platform with long-term adaptive memory. It is designed to run in production environments with strict data isolation, high write concurrency, and reliable, self-correcting retrieval capabilities. 

This document serves as the complete, exhaustive reference blueprint for rebuilding both the backend services and the user interface from scratch.

---

## 2. Global Architecture & Stack Reference

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 Client-Side User Interface                              │
│                      [React + Tailwind CSS + TanStack Start (SSR)]                      │
│                                                                                        │
│   ┌────────────────────────┐  ┌─────────────────────────┐  ┌───────────────────────┐   │
│   │ TanStack Router        │  │ TanStack Query          │  │ Pipeline Lens         │   │
│   │ - Type-Safe Navigation │  │ - SSE Streams & Cache   │  │ - Telemetry Visuals   │   │
│   └────────────────────────┘  └─────────────────────────┘  └───────────────────────┘   │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                  SSE / REST APIs (Port 8000)
                                            │
┌───────────────────────────────────────────▼────────────────────────────────────────────┐
│                                 API & Routing Gateway                                  │
│                                [FastAPI + Uvicorn Server]                              │
│                                                                                        │
│   ┌────────────────────────┐  ┌─────────────────────────┐  ┌───────────────────────┐   │
│   │ JWT & RBAC Middleware  │  │ Celery Task Producer    │  │ Guardrails AI Shield  │   │
│   │ - User & Team Context  │  │ - Offloads to Redis     │  │ - In / Out Validation │   │
│   └────────────────────────┘  └─────────────────────────┘  └───────────────────────┘   │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                      ┌─────────────────────┼─────────────────────┐
                      │                     │                     │
                      ▼                     ▼                     ▼
            ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
            │   LangGraph Engine│ │  Docling Ingest   │ │ Langfuse Registry │
            │   - Agentic RAG   │ │  - Layout Parsing │ │ - Prompt Versions │
            │   - CRAG & Fallback│ │  - Chunker        │ │ - Trace Telemetry │
            └─────────┬─────────┘ └─────────┬─────────┘ └─────────┬─────────┘
                      │                     │                     │
                      └──────────────┬──────┴─────────────────────┘
                                     │
                      ┌──────────────┼────────────────────────────┐
                      │              │                            │
                      ▼              ▼                            ▼
               ┌──────────────┐┌──────────────┐            ┌──────────────┐
               │    MySQL     ││   Weaviate   │            │    Neo4j     │
               │ Relational DB││ Vector Store │            │ Graph Store  │
               │ (Metadata)   ││ (Multi-Tenant│            │ (Multi-DB    │
               │              ││  Sharding)   │            │ Segregation) │
               └──────────────┘└──────────────┘            └──────────────┘
```

---

## 3. Database Schemas & Storage Design

### 3.1 MySQL Relational Schema (DDL)
MySQL serves as the metadata, session, auth, and audit store. The database dialect is optimized for InnoDB with strict indexing.

```sql
-- Disable foreign key checks temporarily to drop tables in correct order during resets
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS crawl_jobs;
DROP TABLE IF EXISTS entity_resolution_log;
DROP TABLE IF EXISTS router_log;
DROP TABLE IF EXISTS vector_chunks;
DROP TABLE IF EXISTS source_docs;
DROP TABLE IF EXISTS turns;
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS team_members;
DROP TABLE IF EXISTS teams;
DROP TABLE IF EXISTS users;
SET FOREIGN_KEY_CHECKS = 1;

-- 1. Users Table
CREATE TABLE users (
    user_id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    global_role VARCHAR(20) NOT NULL DEFAULT 'user', -- 'user', 'admin', 'superadmin'
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Teams Table
CREATE TABLE teams (
    team_id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Team Members Table (Many-to-Many, Per-membership Roles)
CREATE TABLE team_members (
    membership_id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    team_id VARCHAR(36) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user', -- 'user', 'team_lead'
    added_by VARCHAR(36),
    added_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_team (user_id, team_id),
    CONSTRAINT fk_tm_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_tm_team FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
    CONSTRAINT fk_tm_added_by FOREIGN KEY (added_by) REFERENCES users(user_id) ON DELETE SET NULL,
    INDEX idx_tm_team_user (team_id, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Chat Sessions Table
CREATE TABLE sessions (
    session_id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    team_id VARCHAR(36) NOT NULL,
    title VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    consolidated_at DATETIME NULL,
    CONSTRAINT fk_sess_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_sess_team FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
    INDEX idx_sess_team_user (team_id, user_id),
    INDEX idx_sess_created (created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Chat Turns Table (Conversational History)
CREATE TABLE turns (
    turn_id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    team_id VARCHAR(36) NOT NULL,
    role VARCHAR(20) NOT NULL, -- 'user', 'assistant'
    content LONGTEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_turn_sess FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    CONSTRAINT fk_turn_team FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
    INDEX idx_turn_sess_created (session_id, created_at ASC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Source Documents Registry
CREATE TABLE source_docs (
    doc_id VARCHAR(36) PRIMARY KEY,
    team_id VARCHAR(36) NOT NULL,
    source_type VARCHAR(20) NOT NULL, -- 'url', 'gdrive', 'upload'
    source_ref VARCHAR(1024) NOT NULL, -- File path, URL, or Google Drive file ID
    file_name VARCHAR(255) NOT NULL,
    file_format VARCHAR(50) NOT NULL,
    content_hash VARCHAR(64) NOT NULL, -- SHA-256 for duplicate checking
    uploaded_by VARCHAR(36) NOT NULL,
    crawled_at DATETIME NULL,
    modified_at DATETIME NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- 'pending', 'parsing', 'indexing', 'indexed', 'failed'
    error_message TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_doc_team FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
    CONSTRAINT fk_doc_user FOREIGN KEY (uploaded_by) REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_doc_team_hash (team_id, content_hash),
    INDEX idx_doc_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Vector Chunks Index (Maps vector databases back to relational documents)
CREATE TABLE vector_chunks (
    chunk_id VARCHAR(36) PRIMARY KEY, -- Matches Weaviate UUID exactly
    team_id VARCHAR(36) NOT NULL,
    doc_id VARCHAR(36) NOT NULL,
    importance_score DOUBLE NOT NULL DEFAULT 0.5,
    last_accessed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    page_number INT NULL,
    section_heading VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_chunk_team FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
    CONSTRAINT fk_chunk_doc FOREIGN KEY (doc_id) REFERENCES source_docs(doc_id) ON DELETE CASCADE,
    INDEX idx_chunk_team_doc (team_id, doc_id),
    INDEX idx_chunk_decay (importance_score, last_accessed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. Router Log Table
CREATE TABLE router_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    team_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    query_hash VARCHAR(64) NOT NULL,
    route VARCHAR(20) NOT NULL, -- 'graph', 'vector', 'hybrid', 'web'
    latency_ms INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_rlog_team FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
    CONSTRAINT fk_rlog_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_rlog_team_route (team_id, route)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 9. Entity Resolution (Graph Deduplication) Log Table
CREATE TABLE entity_resolution_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    team_id VARCHAR(36) NOT NULL,
    source_node_id VARCHAR(100) NOT NULL,
    target_node_id VARCHAR(100) NOT NULL,
    merge_reason TEXT NOT NULL,
    resolved_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_er_team FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
    INDEX idx_er_team_nodes (team_id, source_node_id, target_node_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10. Web Crawl / Sync Jobs
CREATE TABLE crawl_jobs (
    job_id VARCHAR(36) PRIMARY KEY,
    team_id VARCHAR(36) NOT NULL,
    triggered_by VARCHAR(36) NOT NULL,
    source_url VARCHAR(1024) NOT NULL,
    status VARCHAR(20) NOT NULL, -- 'running', 'done', 'failed'
    pages_found INT DEFAULT 0,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME NULL,
    CONSTRAINT fk_job_team FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
    CONSTRAINT fk_job_user FOREIGN KEY (triggered_by) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

### 3.2 Weaviate Vector Schema
Weaviate stores text chunk embeddings with native multi-tenancy enabled.

```json
{
  "class": "DocumentChunk",
  "description": "Text chunks extracted from team-scoped enterprise files with vector embeddings.",
  "vectorizer": "text2vec-openai", 
  "moduleConfig": {
    "text2vec-openai": {
      "model": "text-embedding-3-small",
      "type": "text"
    }
  },
  "multiTenancyConfig": {
    "enabled": true
  },
  "properties": [
    {
      "name": "text",
      "dataType": ["text"],
      "description": "Raw text content of the chunk",
      "indexSearchable": true,
      "tokenization": "word"
    },
    {
      "name": "chunk_id",
      "dataType": ["string"],
      "description": "Unique UUID matching the relational database",
      "indexFilterable": true,
      "indexSearchable": false
    },
    {
      "name": "doc_id",
      "dataType": ["string"],
      "description": "The parent document registry ID",
      "indexFilterable": true,
      "indexSearchable": false
    },
    {
      "name": "page_number",
      "dataType": ["int"],
      "description": "The page index where the chunk resides",
      "indexFilterable": true
    },
    {
      "name": "section_heading",
      "dataType": ["string"],
      "description": "Structural section header",
      "indexFilterable": true,
      "indexSearchable": true
    },
    {
      "name": "importance_score",
      "dataType": ["number"],
      "description": "Relevance weight calculated for memory decay",
      "indexFilterable": true
    }
  ]
}
```

---

### 3.3 Neo4j Graph Schema
Neo4j stores knowledge graphs. Physical isolation is enforced by hosting a unique database instance per tenant (e.g. `team-abc`). Inside each database, the schema is defined as follows:

```
Nodes:
  (:Entity {
      id:               STRING,       -- Unique entity identifier (e.g. URI or normalized name)
      name:             STRING,       -- Display name of the entity
      type:             STRING,       -- Category (e.g. Person, Organization, Location, Technology)
      importance_score: FLOAT,        -- Modified dynamically by interactions and decay algorithms
      source_doc_id:    STRING,       -- ID of source document generating this entity
      created_at:       STRING        -- ISO DateTime
  })

Relationships:
  (:Entity)-[:RELATES_TO {
      type:             STRING,       -- Relationship definition (e.g. EMPLOYED_BY, FOUNDED, LOCATED_IN)
      weight:           FLOAT,        -- Connection strength (0.0 to 1.0)
      created_at:       STRING,       -- ISO DateTime
      source:           STRING        -- 'ingestion' | 'session_consolidation'
  }]->(:Entity)
```

---

## 4. API Specification & HTTP Routes

All endpoints (except `/health` and `/auth/login`) require a valid Bearer JWT token. The request context must supply an `X-Active-Team-ID` header, which is validated against the user's memberships.

### 4.1 Authentication & Profile
*   **`POST /api/auth/register`**
    *   **Body:** `{"email": "user@example.com", "password": "securepassword"}`
    *   **Response (201):** `{"user_id": "uuid-string", "email": "user@example.com"}`
*   **`POST /api/auth/login`**
    *   **Body:** `{"email": "user@example.com", "password": "securepassword"}`
    *   **Response (200):** `{"token": "jwt-token-string", "refresh_token": "refresh-token-string"}`
*   **`POST /api/auth/refresh`**
    *   **Body:** `{"refresh_token": "refresh-token-string"}`
    *   **Response (200):** `{"token": "new-jwt-token-string"}`

### 4.2 Team & Membership Administration
*   **`POST /api/admin/teams`** (Admin/Superadmin only)
    *   **Body:** `{"name": "Team Alpha", "description": "Engineering team data space"}`
    *   **Response (201):** `{"team_id": "uuid-string", "name": "Team Alpha"}`
*   **`GET /api/me/teams`**
    *   **Response (200):** `[{"team_id": "uuid-string", "name": "Team Alpha", "role": "team_lead"}]`
*   **`POST /api/team/{team_id}/members`** (Team Lead / Admin)
    *   **Body:** `{"email": "newuser@example.com", "role": "user"}`
    *   **Response (200):** `{"membership_id": "uuid-string", "user_id": "uuid-string", "role": "user"}`
*   **`DELETE /api/team/{team_id}/members/{user_id}`** (Team Lead / Admin)
    *   **Response (204):** No Content

### 4.3 Ingestion & Job Management
*   **`POST /api/team/{team_id}/ingest/upload`** (Team Lead / Admin)
    *   **Content-Type:** `multipart/form-data`
    *   **Form Param:** `file: UploadFile`
    *   **Response (201):** `{"doc_id": "uuid-string", "filename": "specs.pdf", "status": "pending"}`
*   **`POST /api/team/{team_id}/ingest/url`** (Team Lead / Admin)
    *   **Body:** `{"url": "https://docs.example.com", "max_depth": 2, "max_pages": 50}`
    *   **Response (201):** `{"job_id": "uuid-string", "url": "https://docs.example.com", "status": "running"}`
*   **`GET /api/team/{team_id}/ingest/status/{job_id_or_doc_id}`**
    *   **Response (200):** `{"id": "uuid", "type": "document|crawl", "status": "indexed|failed|running", "error": null}`
*   **`GET /api/team/{team_id}/docs`**
    *   **Response (200):** `[{"doc_id": "uuid", "file_name": "specs.pdf", "status": "indexed", "created_at": "..."}]`

### 4.4 Agentic Querying (SSE Stream)
*   **`POST /api/query`**
    *   **Header Required:** `X-Active-Team-ID: <team_id>`
    *   **Body:**
        ```json
        {
          "session_id": "optional-uuid-to-continue-session",
          "query": "Who is the lead developer of project Titan?"
        }
        ```
    *   **Response (200):** `text/event-stream` returning NDJSON chunks:
        ```jsonc
        // Event type 1: Telemetry Updates (Pipeline Lens)
        {"type": "telemetry", "stage": "router", "status": "routing to hybrid", "timestamp": "..."}
        {"type": "telemetry", "stage": "graph_traversal", "hops": 2, "entities": ["Titan"]}
        {"type": "telemetry", "stage": "crag_eval", "status": "relevance 0.4 - triggering web search"}
        
        // Event type 2: Text response segments
        {"type": "text_chunk", "content": "The lead developer "}
        {"type": "text_chunk", "content": "is Jane Doe."}
        
        // Event type 3: Citation tracking
        {"type": "citation", "source": "vector", "doc_name": "Project_Titan_Spec.pdf", "page": 2}
        {"type": "citation", "source": "graph", "triple": ["Jane Doe", "LEADS", "Project Titan"]}
        {"type": "citation", "source": "web", "url": "https://press.example.com/titan"}
        
        // Event type 4: Session allocation & Done
        {"type": "session", "session_id": "uuid-assigned-to-chat"}
        {"type": "done"}
        ```

---

## 5. Agentic Orchestrator & LangGraph Implementation

The core query logic is managed via a stateful execution graph in **LangGraph**. The workflow dynamically chooses retrieval mechanisms, validates context relevance, launches corrective fallback searches, and streams outputs.

```
                  ┌──────────────────────┐
                  │      Start Node      │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │    Input Guard       │
                  │ (Guardrails AI Check)│
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │    Query Rewriter    │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │     Query Router     │
                  └──────────┬───────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                ▼                ▼
     [Route: Vector]  [Route: Graph]   [Route: Hybrid]
            │                │                │
            ▼                ▼                ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │Vector Retrieve│ │Graph Retrieve│ │Hybrid Retrieve│
     └────────┬──────┘ └────────┬──────┘ └────────┬──────┘
              │                 │                 │
              └─────────────────┼─────────────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │    CRAG Evaluator    │
                     └──────────┬───────────┘
                                │
            ┌───────────────────┴───────────────────┐
            │ [Relevance Score < Threshold]         │ [Relevance Score >= Threshold]
            ▼                                       ▼
 ┌──────────────────────┐                ┌──────────────────────┐
 │ DuckDuckGo Web Search│                │ Reranking & Fusion   │
 └──────────┬───────────┘                └──────────┬───────────┘
            │                                       │
            ▼                                       │
 ┌──────────────────────┐                           │
 │ Document Integration │                           │
 └──────────┬───────────┘                           │
            │                                       │
            └───────────────────┬───────────────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │   Synthesis Agent    │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │     Output Guard     │
                     │(Guardrails AI Output)│
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │       End Node       │
                     └──────────────────────┘
```

### 5.1 LangGraph State Schema
```python
from typing import TypedDict, List, Dict, Any

class AgentState(TypedDict):
    query: str
    rewritten_queries: List[str]
    active_team_id: str
    user_id: str
    session_id: str
    route: str                           # 'vector' | 'graph' | 'hybrid'
    retrieved_chunks: List[Dict[str, Any]] # Collected text segments
    retrieved_triples: List[List[str]]   # Graph relationships [Subject, Predicate, Object]
    web_search_results: List[Dict[str, Any]]
    final_context: List[Dict[str, Any]]  # Combined, fused, and reranked context
    raw_response: str
    citations: List[Dict[str, Any]]
    relevance_pass: bool                 # Result of the CRAG check
```

### 5.2 Corrective RAG (CRAG) Evaluator Node
The CRAG node evaluates retrieved context against the user queries to ensure grounding.

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

class RelevanceGrade(BaseModel):
    score: float = Field(description="Normalized relevance score between 0.0 (completely irrelevant) and 1.0 (fully sufficient)")
    reasoning: str = Field(description="Reasoning explaining the decision")

def evaluate_retrieval(state: AgentState) -> Dict[str, Any]:
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash").with_structured_output(RelevanceGrade)
    
    prompt = ChatPromptTemplate.from_template(
        "You are an evaluator. Determine if the following retrieved context is sufficient and relevant "
        "to answer the user query.\n\n"
        "User Query: {query}\n\n"
        "Retrieved Context:\n{context}\n\n"
        "Assess relevance honestly. Provide a score from 0.0 to 1.0."
    )
    
    context_str = "\n".join([chunk["text"] for chunk in state["retrieved_chunks"]])
    chain = prompt | llm
    result = chain.invoke({"query": state["query"], "context": context_str})
    
    # Threshold condition: score >= 0.5 passes
    return {
        "relevance_pass": result.score >= 0.5,
        "telemetry_log": f"CRAG score: {result.score}. Reasoning: {result.reasoning}"
    }
```

### 5.3 DuckDuckGo Search Integration Node
Invoked only when `relevance_pass` is False.

```python
from langchain_community.tools import DuckDuckGoSearchRun

def web_search_fallback(state: AgentState) -> Dict[str, Any]:
    search = DuckDuckGoSearchRun()
    search_query = state["rewritten_queries"][0] if state["rewritten_queries"] else state["query"]
    
    # Execute search
    web_raw = search.run(search_query)
    
    # Format search results as pseudo-chunks
    web_chunks = [{
        "text": web_raw,
        "source": "web",
        "url": "https://html.duckduckgo.com/html/?q=" + search_query,
        "score": 0.8
    }]
    
    return {"web_search_results": web_chunks}
```

---

## 6. Document Ingestion Pipeline with Docling

The document ingestion pipeline parses enterprise file formats, converts layout structures into clean representations, chunks text safely, and writes outputs to database engines.

```
[Raw Document File]
       │
       ▼
┌──────────────┐
│Docling Parser│ ──► Extracts text, column structures, and reading order
└──────┬───────┘
       │
       ▼
┌──────────────┐
│Table Compiler│ ──► Converts tabular data structures to Markdown tables
└──────┬───────┘
       │
       ▼
┌──────────────┐
│Text Chunker  │ ──► Splits layout using Recursive Character Chunker
└──────┬───────┘     (512 token limit, 64 token overlap)
       │
       ▼
┌──────────────┐
│Embedding Gen │ ──► Generates vector embeddings using text-embedding-3-small
└──────┬───────┘
       ├─────────────────────────────────┐
       ▼                                 ▼
┌──────────────┐                 ┌──────────────┐
│  Weaviate    │                 │    Neo4j     │
│  Ingestion   │                 │  Ingestion   │
│  (Tenant     │                 │ (Dynamic DB  │
│  Targeted)   │                 │  Selection)  │
└──────────────┘                 └──────────────┘
```

### 6.1 Ingestion Script Skeleton
```python
from docling.document_converter import DocumentConverter
from langchain_text_splitters import RecursiveCharacterTextSplitter
from weaviate import Client
from neo4j import GraphDatabase

def ingest_document(file_path: str, team_id: str, doc_id: str, weaviate_client: Client, neo4j_driver: GraphDatabase.driver):
    # 1. Parse Document using Docling
    converter = DocumentConverter()
    result = converter.convert(file_path)
    # Get layout-aware Markdown representation
    markdown_content = result.document.export_to_markdown()
    
    # 2. Chunking
    splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=64)
    chunks = splitter.split_text(markdown_content)
    
    # 3. Write to Weaviate (Scoped by team tenant)
    for index, chunk_text in enumerate(chunks):
        chunk_uuid = generate_deterministic_uuid(doc_id, index)
        
        weaviate_client.data_object.create(
            data_object={
                "text": chunk_text,
                "chunk_id": chunk_uuid,
                "doc_id": doc_id,
                "page_number": int(index / 2) + 1, # Estimated fallback
                "section_heading": "Structured Document Section",
                "importance_score": 1.0
            },
            class_name="DocumentChunk",
            tenant=team_id, # Target tenant shard directly
            uuid=chunk_uuid
        )
        
        # Keep registry in relational db
        record_chunk_in_mysql(chunk_uuid, team_id, doc_id, index)

    # 4. Entity & Relationship Graph Extraction (Dynamic Neo4j Selection)
    entities, relations = extract_graph_triples_via_llm(markdown_content)
    
    # neo4j_driver allows connecting to a specific tenant DB directly
    with neo4j_driver.session(database=f"team-{team_id}") as session:
        for ent in entities:
            session.run(
                "MERGE (e:Entity {id: $id}) "
                "ON CREATE SET e.name = $name, e.type = $type, e.importance_score = 1.0, e.source_doc_id = $doc_id, e.created_at = datetime()",
                {"id": ent["id"], "name": ent["name"], "type": ent["type"], "doc_id": doc_id}
            )
        for rel in relations:
            session.run(
                "MATCH (a:Entity {id: $source_id}), (b:Entity {id: $target_id}) "
                "MERGE (a)-[r:RELATES_TO {type: $type}]->(b) "
                "ON CREATE SET r.weight = 1.0, r.created_at = datetime(), r.source = 'ingestion'",
                {"source_id": rel["source"], "target_id": rel["target"], "type": rel["type"]}
            )
```

### 6.2 Task Queue & Background Worker Architecture (Celery + Redis)

To prevent resource contention and API timeouts on the FastAPI web server, all CPU-heavy and I/O-heavy background tasks are fully offloaded to **Celery workers** using **Redis** as a message broker.

#### 6.2.1 Celery Application Setup (`backend/tasks/celery_app.py`)
```python
import os
from celery import Celery
from celery.schedules import crontab

# Configure Redis as both the message broker and task result backend
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "memmesh_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks.jobs"]
)

# Operational configs
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,  # 30 minutes absolute time limit
)

# Periodic Tasks Configuration (Celery Beat Scheduler)
celery_app.conf.beat_schedule = {
    "daily-memory-decay-job": {
        "task": "tasks.jobs.decay_memory_task",
        "schedule": crontab(hour=0, minute=0), # Run daily at midnight UTC
    },
    "weekly-entity-resolution-job": {
        "task": "tasks.jobs.entity_resolution_task",
        "schedule": crontab(day_of_week=0, hour=2, minute=0), # Run Sundays at 2:00 AM UTC
    },
}
```

#### 6.2.2 Task Definitions (`backend/tasks/jobs.py`)
```python
import os
import shutil
from typing import Dict, Any
from pathlib import Path
from tasks.celery_app import celery_app
from ingestion.parser import ingest_document
from db.weaviate import get_weaviate_client
from db.neo4j import get_neo4j_driver
from db.mysql import get_mysql_connection

@celery_app.task(name="tasks.jobs.ingest_doc_task", bind=True, max_retries=3)
def ingest_doc_task(self, team_id: str, doc_id: str, file_path: str):
    """
    Task to execute Docling parsing, chunking, Weaviate embedding, and Neo4j creation.
    Offloaded from POST /api/team/{team_id}/ingest/upload.
    """
    self.update_state(state="PROGRESS", meta={"status": "Parsing document layout via Docling"})
    
    # Establish dynamic database drivers
    weaviate_client = get_weaviate_client()
    neo4j_driver = get_neo4j_driver()
    
    try:
        # Run parsing and DB ingestion
        ingest_document(
            file_path=file_path,
            team_id=team_id,
            doc_id=doc_id,
            weaviate_client=weaviate_client,
            neo4j_driver=neo4j_driver
        )
        
        # Update status in MySQL to indexed
        update_doc_status_in_mysql(doc_id, "indexed")
        
        # Clean up local temp file
        if os.path.exists(file_path):
            os.remove(file_path)
            
        return {"status": "success", "doc_id": doc_id}
        
    except Exception as exc:
        update_doc_status_in_mysql(doc_id, "failed", error_message=str(exc))
        # Retry logic for network/database blips
        raise self.retry(exc=exc, countdown=60)

@celery_app.task(name="tasks.jobs.decay_memory_task")
def decay_memory_task():
    """
    Daily job to prune old vector chunks and low-degree nodes based on importance_score.
    """
    mysql_conn = get_mysql_connection()
    weaviate_client = get_weaviate_client()
    neo4j_driver = get_neo4j_driver()
    
    # Iterate through each active team
    teams = fetch_all_teams_mysql(mysql_conn)
    for team in teams:
        team_id = team["team_id"]
        # 1. Decay vectors in Weaviate for the team
        decay_vectors_in_weaviate(weaviate_client, team_id)
        # 2. Prune low-degree nodes in the team's Neo4j database
        prune_neo4j_graph(neo4j_driver, team_id)

@celery_app.task(name="tasks.jobs.entity_resolution_task")
def entity_resolution_task():
    """
    Weekly job running entity deduplication and merging inside individual team graphs.
    """
    neo4j_driver = get_neo4j_driver()
    mysql_conn = get_mysql_connection()
    
    teams = fetch_all_teams_mysql(mysql_conn)
    for team in teams:
        team_id = team["team_id"]
        # Execute merging logic on team's Neo4j DB
        run_entity_resolution_for_team(neo4j_driver, team_id)
```

#### 6.2.3 Offloading Logic in API Routes
FastAPI endpoints push workloads immediately to the queue:
```python
# In backend/api/routes/ingest.py
@router.post("/ingest/upload", status_code=201)
async def upload_document(
    team_id: str,
    file: UploadFile = File(...),
    conn = Depends(get_mysql_db),
    current_user = Depends(require_team_role("lead"))
):
    # Register document as 'pending' in MySQL
    doc_id = register_pending_doc_in_mysql(conn, team_id, file.filename)
    
    # Write file to temp upload location
    temp_path = save_temp_upload(file, team_id)
    
    # Push job to Celery Worker
    task = ingest_doc_task.delay(team_id, doc_id, temp_path)
    
    return {"doc_id": doc_id, "task_id": task.id, "status": "pending"}
```

---

## 7. Guardrails & Observability Integration

### 7.1 Input/Output Safety with Guardrails AI
We configure `guardrails-ai` validation rails before execution queries and after synthesis pipelines.

```python
import guardrails as gd
from guardrails.hub import ValidRange, ToxicLanguage, PiiFilter

# Input safety guards
input_guard = gd.Guard().use_many(
    PiiFilter(on_fail="fix"),                      # Scrub phone numbers, emails, addresses
    ToxicLanguage(threshold=0.8, on_fail="exception") # Prevent offensive/unsafe prompts
)

# Output hallucination and conformance guards
# (e.g. check_context_conformance dynamically using guardrails schemas)
```

### 7.2 DeepEval Unit Testing Assertions
DeepEval guarantees system quality with structured testing parameters before codebase merges.

```python
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import HallucinationMetric, FaithfulnessMetric, AnswerRelevancyMetric

def test_rag_synthesis_quality():
    # Construct standard reference parameters
    actual_output = "Jane Doe is the lead engineer of Project Titan."
    retrieved_context = ["Jane Doe was appointed lead engineer on Project Titan in Q1 2026."]
    input_query = "Who leads Project Titan?"
    
    test_case = LLMTestCase(
        input=input_query,
        actual_output=actual_output,
        retrieved_context=retrieved_context
    )
    
    # 1. Faithfulness Metric Assertion
    faithfulness_metric = FaithfulnessMetric(threshold=0.7)
    
    # 2. Hallucination Metric Assertion
    hallucination_metric = HallucinationMetric(threshold=0.5)
    
    assert_test(test_case, [faithfulness_metric, hallucination_metric])
```

### 7.3 Langfuse Observability Telemetry
Langfuse monitors tracing metadata and prompt management dynamically.

```python
from langfuse import Langfuse

langfuse = Langfuse()

def trace_langgraph_step(step_name: str, input_data: Any, output_data: Any, session_id: str, trace_id: str):
    # Export spans directly to the trace tree
    langfuse.span(
        trace_id=trace_id,
        name=step_name,
        input=input_data,
        output=output_data,
        session_id=session_id
    )
```

---

## 8. Frontend Interface Design (React + TanStack)

The user interface is built as a highly responsive, real-time application using **React**, **Tailwind CSS**, and **TanStack Start**.

### 8.1 Streaming Message SSE Hook (TanStack Query compatible)
```tsx
import { useState } from 'react';

export function useSSEQuery() {
  const [data, setData] = useState<string>('');
  const [telemetry, setTelemetry] = useState<any[]>([]);
  const [citations, setCitations] = useState<any[]>([]);

  const executeQuery = async (queryText: string, activeTeamId: string, sessionId?: string) => {
    setData('');
    setTelemetry([]);
    setCitations([]);

    const response = await fetch('/api/query', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Active-Team-ID': activeTeamId,
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify({ query: queryText, session_id: sessionId })
    });

    if (!response.body) return;
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Keep partial line in buffer

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const chunk = JSON.parse(line);
          if (chunk.type === 'text_chunk') {
            setData((prev) => prev + chunk.content);
          } else if (chunk.type === 'telemetry') {
            setTelemetry((prev) => [...prev, chunk]);
          } else if (chunk.type === 'citation') {
            setCitations((prev) => [...prev, chunk]);
          }
        } catch (e) {
          console.error("Failed to parse SSE line", e);
        }
      }
    }
  };

  return { executeQuery, data, telemetry, citations };
}
```

---

## 9. Comprehensive Workspace Folder Structure

The following tree represents the complete target workspace directory layout. All configuration, source code, task definitions, and tests are isolated in their respective domains.

```
/home/ritesh/workspace/MemMesh/
├── backend/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── server.py                 # FastAPI application factory & lifespan manager
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── admin.py              # Team provision & system monitoring routes
│   │       ├── auth.py               # Session management & credential validation
│   │       ├── ingest.py             # File uploads, crawling, & sync trigger routes
│   │       └── query.py              # LangGraph query triggers (SSE Streaming endpoint)
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── jwt.py                # Token generation & key decryption routines
│   │   ├── middleware.py         # Tenant verification and global role validations
│   │   └── passwords.py          # Hashing utility using bcrypt
│   ├── db/
│   │   ├── __init__.py
│   │   ├── mysql.py              # InnoDB connection pooling & dynamic context managers
│   │   ├── weaviate.py           # Client schema setups and multi-tenant shard drivers
│   │   ├── neo4j.py              # Dynamic DB context mapper routing by team_id
│   │   └── migrations/
│   │       ├── 001_init.sql          # Base users, teams, and memberships tables
│   │       ├── 002_sessions.sql      # MySQL schema migration for chat history turns
│   │       └── 003_source_docs.sql   # Document registry and crawler log indexes
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── parser.py             # Docling converter integrations (layout & tables)
│   │   └── chunker.py            # Recursive character splitting logic
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── graph_orchestrator.py # Core LangGraph state machines definitions
│   │   ├── router.py             # LLM query path classifier node
│   │   ├── rewriter.py           # Gemini step-back query generator node
│   │   ├── crag.py               # Retrieval evaluation checks node (CRAG)
│   │   ├── web_search.py         # DuckDuckGo query integration tool node
│   │   └── safety.py             # Input/Output Guardrails AI shield models
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── celery_app.py         # Celery instance configurations and beat crons
│   │   └── jobs.py               # Ingestion, crawling, decay, and resolution jobs
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py           # DB mocks, test lifespans, and fixtures
│   │   ├── test_mysql_conn.py    # DDL & handshake connection validation
│   │   ├── test_auth.py          # Session auth and context check validations
│   │   ├── test_ingest.py        # Docling parser and chunker unit verifications
│   │   ├── test_graph.py         # LangGraph routes execution integration checks
│   │   ├── test_crag.py          # Evaluation and search fallback integration checks
│   │   └── test_safety.py        # Guardrails validator logic checks
│   ├── .env.example              # Key/Value templates for configurations
│   ├── config.py                 # Env variable loaders and validations
│   ├── docker-compose.yml        # Orchestration files for Weaviate, Neo4j, Redis, MySQL
│   ├── Makefile                  # Local automation tasks
│   ├── requirements.txt          # Python pip dependencies list
│   └── main.py                   # Uvicorn boot entrypoint
├── frontend/
│   ├── src/
│   │   ├── routes/
│   │   │   ├── __root.tsx        # Base root provider layout with active theme context
│   │   │   ├── index.tsx         # Root endpoint routing to home layout
│   │   │   └── dashboard/
│   │   │       ├── layout.tsx     # Workspace sidebar, status, & switcher
│   │   │       ├── index.tsx      # Team dashboards overview
│   │   │       ├── chat.tsx       # Live chat stream windows
│   │   │       ├── documents.tsx  # Document browsers and preview splits
│   │   │       └── admin/
│   │   │           ├── teams.tsx  # Admin configuration for teams list
│   │   │           └── users.tsx  # Admin credentials list
│   │   ├── components/
│   │   │   ├── ui/                # Small Tailwind primitives (buttons, inputs)
│   │   │   │   ├── button.tsx
│   │   │   │   ├── card.tsx
│   │   │   │   ├── drawer.tsx
│   │   │   │   └── dialog.tsx
│   │   │   ├── pipeline-lens.tsx  # Stream stage tracking visuals
│   │   │   ├── preview-panel.tsx  # Canvas PDF and text viewing panels
│   │   │   └── citation-drawer.tsx# Slide-out source details panel
│   │   ├── lib/
│   │   │   ├── api.ts             # REST client using Axios
│   │   │   └── theme.ts           # State switcher for theme settings
│   │   ├── styles/
│   │   │   └── global.css         # Tailwind classes
│   │   ├── main.tsx               # App start mounts
│   │   └── vite-env.d.ts
│   ├── tailwind.config.js
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
├── tests/
│   ├── e2e/
│   │   ├── auth.spec.ts           # E2E login and router validation checks
│   │   ├── chat.spec.ts           # E2E SSE stream, lens, and citation checks
│   │   └── doc_browser.spec.ts    # E2E document indexing & preview checks
│   └── fixtures/
│       └── sample.pdf             # Static assets for document uploads
├── playwright.config.ts           # Playwright E2E testing framework configuration (at root)
```

---

## 10. Test-Driven Development (TDD) with Playwright & Pytest

To ensure system reliability, the implementation follows a strict **Test-Driven Development (TDD)** loop:

```
┌────────────────────────────────────────────────────────┐
│                   Write Failing Test                   │
│   (Pytest for Backend / Playwright E2E for Frontend)   │
└───────────────────────────┬────────────────────────────┘
                            │ (Verify Test Fails - RED)
                            ▼
┌────────────────────────────────────────────────────────┐
│             Write Minimal Code to Pass                 │
│         (Implementation fits test assertions)          │
└───────────────────────────┬────────────────────────────┘
                            │ (Test Passes - GREEN)
                            ▼
┌────────────────────────────────────────────────────────┐
│                     Refactor Code                      │
│     (Optimize logic, keep test suites passing)         │
└───────────────────────────┬────────────────────────────┘
                            │ (Verify Clean - REFACTOR)
                            ▼
                     [Next TDD Iteration]
```

### 10.1 Playwright E2E Testing Configuration (`playwright.config.ts`)
Playwright tests are configured at the workspace root to validate client-side behaviors, launching the TanStack Start development server inside the `frontend` folder.

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
  // Launch the TanStack Start dev server inside the frontend subdirectory
  webServer: {
    command: 'npm run --prefix frontend dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
});
```

### 10.2 TDD Frontend Test Example (`tests/e2e/chat.spec.ts`)
This test is written *before* the streaming chat UI is implemented, defining the behavior of message sending, streaming, citations, and the Pipeline Lens.

```typescript
import { test, expect } from '@playwright/test';

test.describe('Agentic Chat & Retrieval telemetry E2E', () => {
  test.beforeEach(async ({ page }) => {
    // 1. Perform mock authentication (login bypass or setup cookie)
    await page.goto('/dashboard/chat');
    await page.context().addInitScript(() => {
      window.localStorage.setItem('token', 'mocked-jwt-token');
    });
    
    // Select Active Team context
    await page.locator('select#active-team-select').selectOption('team-uuid-alpha');
  });

  test('should display streaming agent response and render telemetry in pipeline lens', async ({ page }) => {
    // 1. Assert input field exists and accept query
    const input = page.locator('textarea#chat-query-input');
    await expect(input).toBeVisible();
    await input.fill('Who leading project Titan?');

    // 2. Click send trigger
    const sendButton = page.locator('button#chat-send-btn');
    await sendButton.click();

    // 3. Assert loading telemetry states begin inside Pipeline Lens
    const routerLensNode = page.locator('[data-testid="lens-node-router"]');
    await expect(routerLensNode).toHaveAttribute('data-state', 'active');

    // 4. Assert response is streaming into chat window bubble
    const chatBubble = page.locator('.chat-message-assistant').last();
    await expect(chatBubble).toContainText('The lead developer');

    // 5. Assert Pipeline Lens transitions dynamically
    const cragLensNode = page.locator('[data-testid="lens-node-crag"]');
    await expect(cragLensNode).toHaveAttribute('data-state', 'success');

    // 6. Assert citation slide drawer renders correct source elements
    const citationContainer = page.locator('[data-testid="citation-tag"]');
    await expect(citationContainer).toHaveCount(1);
    await citationContainer.click();

    const drawer = page.locator('[data-testid="citation-details-drawer"]');
    await expect(drawer).toBeVisible();
    await expect(drawer).toContainText('Project_Titan_Spec.pdf');
  });
});
```

---

## 11. Technical Stack Dependency Inventory

The complete catalog of dependencies required for development and production execution:

### 11.1 Backend Dependencies (`backend/requirements.txt`)
*   **FastAPI** (`0.115.0`) & **Uvicorn** (`0.32.0`): Core web framework and ASGI execution container.
*   **Celery** (`5.4.0`) & **Redis** (`5.0.8`): Offloads CPU-intensive workloads; Redis handles messaging broker streams.
*   **SQLAlchemy** (`2.0.35`) & **PyMySQL** (`1.1.1`): Database ORM mapper and MySQL connector driver.
*   **Alembic** (`1.13.3`): Database schema migrations management.
*   **Weaviate-Client** (`4.9.2`): Core gRPC client communication with Weaviate cluster namespaces.
*   **Neo4j** (`5.25.0`): Neo4j graph driver supporting bolt/routing interfaces.
*   **Docling** (`2.97.0`): Unified document layout converter, PDF parser, and OCR engine.
*   **LangGraph** (`0.2.34`) & **LangChain** (`0.3.3`): Agentic state-graph orchestrators.
*   **Guardrails-AI** (`0.5.4`): Content validators, input/output validation checks.
*   **DeepEval** (`0.21.3`): Metrics assertion frameworks (hallucination, faithfulness).
*   **Langfuse** (`2.44.0`): Tracing instrumentation client.
*   **DuckDuckGo-Search** (`6.3.0`): Fallback search query tools.

### 11.2 Frontend Dependencies (`frontend/package.json`)
*   **React** (`18.3.1`) & **React-DOM** (`18.3.1`): UI engine.
*   **Tailwind CSS** (`3.4.13`): Tailwind style engine.
*   **@tanstack/start** (`0.0.1-beta`): SSR full-stack React metadata orchestrator.
*   **@tanstack/react-router** (`1.58.0`): Client routing, pre-loading, and type-safe navigations.
*   **@tanstack/react-query** (`5.59.0`): Server state loader caching layers.
*   **Axios** (`1.7.7`): REST endpoint callers.
*   **lucide-react** (`0.452.0`): Icon vector assets.
*   **pdfjs-dist** (`4.7.76`): PDF parser canvas renderer helper.

---

## 12. Comprehensive 11-Phase Implementation Plan

Each phase details exact developer deliverables, target files, and unit tests to ensure a vertical, verifiable re-build from scratch.

### Phase 1 — Project Initialization & MySQL Setup
*   **Deliverables:** React + Tailwind + TanStack Start frontend structure, FastAPI backend directory skeleton, and MySQL base connections.
*   **Files Created/Modified:**
    *   `backend/db/mysql.py` $\rightarrow$ Create connection pool and transaction manager
    *   `backend/db/migrations/001_init.sql` $\rightarrow$ Write tables for users, teams, and team_members
    *   `frontend/package.json` $\rightarrow$ Install Tailwind, TanStack Start, Router, and Query
*   **Automated Verification:**
    *   `pytest backend/tests/test_mysql_conn.py` $\rightarrow$ Assert successful handshake and DDL application

### Phase 2 — Authentication, Session Profiles, & Context RBAC
*   **Deliverables:** User login/registration REST APIs, JWT validation, and RBAC middleware context verification.
*   **Files Created/Modified:**
    *   `backend/auth/jwt.py` $\rightarrow$ Token signing and decryption
    *   `backend/auth/middleware.py` $\rightarrow$ Parse user ID and target `X-Active-Team-ID` from header; verify user role.
    *   `backend/api/routes/auth.py` $\rightarrow$ `/api/auth/register`, `/api/auth/login`, `/api/auth/refresh`
*   **Automated Verification:**
    *   `pytest backend/tests/test_auth.py` $\rightarrow$ Mock headers; assert 403 on missing team memberships

### Phase 3 — App Shell, Skeletons, & Theme Synchronization
*   **Deliverables:** App navigation frame, team switching dropdowns, and light/dark styling transitions.
*   **Files Created/Modified:**
    *   `frontend/src/routes/__root.tsx` $\rightarrow$ Set light/dark class on base html document
    *   `frontend/src/routes/dashboard/layout.tsx` $\rightarrow$ Sidebar with team switcher component
    *   `frontend/src/lib/theme.ts` $\rightarrow$ Handle dynamic window system theme matches
*   **Automated Verification:**
    *   `playwright test tests/theme_switch.spec.ts` $\rightarrow$ Assert contrast ratios in both light and dark mode classes exceed 4.5:1

### Phase 4 — Docling Parser & Multi-Tenant Database Indexers
*   **Deliverables:** IBM Docling parser integration, vector/graph ingestion loops, and metadata records management.
*   **Files Created/Modified:**
    *   `backend/ingestion/parser.py` $\rightarrow$ Docling converter pipeline
    *   `backend/db/weaviate.py` $\rightarrow$ Create multi-tenant classes and client wrappers
    *   `backend/db/neo4j.py` $\rightarrow$ Dynamic DB connection driver mapping `team_id`
*   **Automated Verification:**
    *   `pytest backend/tests/test_ingest_pipeline.py` $\rightarrow$ Parse sample doc; check Weaviate tenant shard holds vector; check Neo4j instance contains node relationships.

### Phase 5 — Stateful LangGraph Retrieval & Langfuse Registry
*   **Deliverables:** LangGraph flow construction, query routing/rewriting nodes, and Langfuse tracing.
*   **Files Created/Modified:**
    *   `backend/agents/graph_orchestrator.py` $\rightarrow$ LangGraph state definitions and node connections
    *   `backend/agents/router.py` $\rightarrow$ Select vector/graph/hybrid route via Gemini
    *   `backend/agents/rewriter.py` $\rightarrow$ Generate queries rephrasings
*   **Automated Verification:**
    *   `pytest backend/tests/test_router_log.py` $\rightarrow$ Verify routing decisions persist in MySQL and output traces sync to Langfuse.

### Phase 6 — Corrective RAG (CRAG) & Web Search Fallbacks
*   **Deliverables:** CRAG scoring node, relevance evaluator prompts, and DuckDuckGo search fallbacks.
*   **Files Created/Modified:**
    *   `backend/agents/crag.py` $\rightarrow$ Relevance scorer node and logic
    *   `backend/agents/web_search.py` $\rightarrow$ DuckDuckGo execution tool node
*   **Automated Verification:**
    *   `pytest backend/tests/test_crag_flow.py` $\rightarrow$ Feed irrelevant context; assert search fallback is triggered and results are merged into the context list.

### Phase 7 — Guardrails AI Safety Shield & Streaming Synthesis
*   **Deliverables:** Input safety validation, hallucination checking output guards, and SSE stream endpoints.
*   **Files Created/Modified:**
    *   `backend/api/routes/query.py` $\rightarrow$ Streaming response endpoints
    *   `backend/agents/synthesis.py` $\rightarrow$ Gemini SSE chunk streamer
    *   `backend/agents/safety.py` $\rightarrow$ Guardrails AI input/output wrapper schemas
*   **Automated Verification:**
    *   `pytest backend/tests/test_guardrails.py` $\rightarrow$ Try prompt injection; assert validation exceptions are raised and blocked.

### Phase 8 — React Chat Window & Citation Drawers
*   **Deliverables:** Streaming chat view using TanStack Query, SSE chunk assembly UI, and sliding citation inspectors.
*   **Files Created/Modified:**
    *   `frontend/src/routes/dashboard/chat.tsx` $\rightarrow$ SSE stream listener hooks
    *   `frontend/src/components/citation-drawer.tsx` $\rightarrow$ Render details of the current citation
*   **Automated Verification:**
    *   `playwright test tests/chat_streaming.spec.ts` $\rightarrow$ Assert stream renders tokens sequentially and citation details match payloads.

### Phase 9 — Real-time Pipeline Lens & Trace Audits
*   **Deliverables:** Step-by-step telemetry visualizations and historical trace review panels.
*   **Files Created/Modified:**
    *   `frontend/src/components/pipeline-lens.tsx` $\rightarrow$ Render active retrieval milestones
    *   `frontend/src/routes/dashboard/documents.tsx` $\rightarrow$ Panel listing files and metrics
*   **Automated Verification:**
    *   `playwright test tests/pipeline_lens.spec.ts` $\rightarrow$ Check that telemetry events display correct states (router -> retrieve -> crag -> synthesis).

### Phase 10 — DeepEval Testing & Memory Decays
*   **Deliverables:** DeepEval metric assertions, Celery Beat periodic task schedules, and memory decay/entity resolution tasks.
*   **Files Created/Modified:**
    *   `backend/tasks/celery_app.py` $\rightarrow$ Setup Celery application and periodic task mappings
    *   `backend/tasks/jobs.py` $\rightarrow$ Define worker task logic for decay and entity resolution
    *   `backend/tests/test_deepeval_rag.py` $\rightarrow$ Assertions script
*   **Automated Verification:**
    *   `make test-eval` $\rightarrow$ Execute DeepEval metrics; assert that Faithfulness and Answer Relevancy scores exceed 0.7.

### Phase 11 — Hardening, E2E Auditing, & Production Build
*   **Deliverables:** WCAG accessibility checks, keyboard navigations, and optimization.
*   **Files Created/Modified:**
    *   `backend/Makefile` $\rightarrow$ Add setup targets, Celery launch targets, and database migrations
    *   `backend/docker-compose.yml` $\rightarrow$ Configure MySQL, Weaviate, Neo4j, Redis, and Celery Worker containers
*   **Automated Verification:**
    *   `make test` $\rightarrow$ Complete backend tests suite runs successfully
    *   `make test-e2e` $\rightarrow$ E2E frontend flows pass without errors

