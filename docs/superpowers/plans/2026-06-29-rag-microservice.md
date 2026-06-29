# RAG Microservice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `hybrid-rag/` as a clean FastAPI microservice that accepts configurable Hybrid/Semantic/Lexical RAG modes and switches between Gemini and Ollama via `.env`.

**Architecture:** FastAPI server with a `/query` endpoint (runs the LangGraph pipeline) and a `/ingest` endpoint (adds documents to FAISS + BM25 indices). The LLM provider (Gemini or Ollama) is resolved at startup from `LLM_PROVIDER` env var via a factory. All benchmark/research artifacts are deleted.

**Tech Stack:** Python 3.11, FastAPI, Uvicorn, LangGraph, LangChain, FAISS, BM25Okapi, sentence-transformers, `langchain-google-genai` (Gemini), `langchain-ollama` (Ollama), Pydantic v2, python-dotenv.

> **tRPC note:** tRPC is TypeScript-only. This service is Python; FastAPI gives you auto-generated OpenAPI docs + type safety via codegen for any TypeScript caller. tRPC would require a full rewrite in Node.js with no benefit over FastAPI + OpenAPI here.

## Global Constraints

- Python 3.11+
- No benchmark/evaluation code of any kind in the final service
- LLM choice is controlled exclusively by `LLM_PROVIDER` env var — no code changes required to switch
- Per-request config overrides are allowed (mode, top_k, weights) but defaults come from `.env`
- `src/` package layout is preserved; only research-only files at the root are deleted

---

## File Map

**Delete:**
- `adversarial_data.py`
- `benchmark_report.md`
- `benchmark_results.png`
- `retrieval_results_2k.json`
- `run_benchmark.py`
- `conference_101719_REVISED.tex`
- `src/evaluation/` (entire directory)
- `README.md` (replaced)

**Rewrite:**
- `src/core/config.py` — LLM + RAG settings from env
- `src/domain/retrieval/retriever.py` — add `add_documents()`
- `src/pipeline/graph.py` — inject LLM, remove benchmark artifacts (`skip_generation`)
- `requirements.txt` — clean, no research deps

**Create:**
- `.env.example`
- `src/llm/__init__.py`
- `src/llm/factory.py` — returns Gemini or Ollama LLM
- `src/api/__init__.py`
- `src/api/schemas.py` — Pydantic request/response models
- `src/api/routes/__init__.py`
- `src/api/routes/ingest.py`
- `src/api/routes/query.py`
- `src/api/app.py` — FastAPI lifespan + router wiring
- `Dockerfile`
- `README.md`

---

### Task 1: Delete research files

**Files:**
- Delete: `adversarial_data.py`, `benchmark_report.md`, `benchmark_results.png`, `retrieval_results_2k.json`, `run_benchmark.py`, `conference_101719_REVISED.tex`, `src/evaluation/`

- [ ] **Step 1: Delete root-level research artifacts**

```bash
cd hybrid-rag
rm adversarial_data.py benchmark_report.md benchmark_results.png retrieval_results_2k.json run_benchmark.py conference_101719_REVISED.tex
```

- [ ] **Step 2: Delete evaluation module**

```bash
rm -rf src/evaluation
```

- [ ] **Step 3: Verify only essential source remains**

```bash
find src -type f
# Expected:
# src/core/config.py
# src/domain/reranking/cross_encoder.py
# src/domain/retrieval/retriever.py
# src/pipeline/graph.py
```

- [ ] **Step 4: Delete the old Cursor plan file**

```bash
rm -f ../.cursor/plans/finrisk_tdd_implementation_12f1d804.plan.md
# (path relative to financeKit root)
rm -f /home/yasser/Desktop/Big-5/financeKit/volatility-ms/.cursor/plans/finrisk_tdd_implementation_12f1d804.plan.md
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: delete all research/benchmark artifacts from hybrid-rag"
```

---

### Task 2: Rewrite config.py and requirements.txt

**Files:**
- Modify: `src/core/config.py`
- Modify: `requirements.txt`
- Create: `.env.example`

**Interfaces:**
- Produces: `Config.LLM_PROVIDER: str`, `Config.GEMINI_API_KEY: str`, `Config.GEMINI_MODEL: str`, `Config.OLLAMA_BASE_URL: str`, `Config.OLLAMA_MODEL: str`, `Config.EMBEDDING_MODEL: str`, `Config.CROSS_ENCODER_MODEL: str`, `Config.RAG_MODE: str`, `Config.TOP_K: int`, `Config.SEMANTIC_WEIGHT: float`, `Config.LEXICAL_WEIGHT: float`, `Config.ENABLE_RERANK: bool`, `Config.CACHE_DIR: str`, `Config.validate() -> None`

- [ ] **Step 1: Rewrite `src/core/config.py`**

```python
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    CROSS_ENCODER_MODEL: str = os.getenv("CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

    RAG_MODE: str = os.getenv("RAG_MODE", "hybrid")
    TOP_K: int = int(os.getenv("TOP_K", "3"))
    SEMANTIC_WEIGHT: float = float(os.getenv("SEMANTIC_WEIGHT", "0.7"))
    LEXICAL_WEIGHT: float = float(os.getenv("LEXICAL_WEIGHT", "0.3"))
    ENABLE_RERANK: bool = os.getenv("ENABLE_RERANK", "true").lower() == "true"
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))

    CACHE_DIR: str = os.getenv("CACHE_DIR", "cache")

    @classmethod
    def validate(cls) -> None:
        if cls.LLM_PROVIDER not in ("ollama", "gemini"):
            raise ValueError(f"LLM_PROVIDER must be 'ollama' or 'gemini', got: {cls.LLM_PROVIDER!r}")
        if cls.LLM_PROVIDER == "gemini" and not cls.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        if cls.RAG_MODE not in ("hybrid", "semantic", "lexical"):
            raise ValueError(f"RAG_MODE must be hybrid/semantic/lexical, got: {cls.RAG_MODE!r}")
```

- [ ] **Step 2: Rewrite `requirements.txt`**

```
fastapi
uvicorn[standard]
python-dotenv
langchain
langchain-core
langchain-community
langchain-huggingface
langchain-ollama
langchain-google-genai
langgraph
sentence-transformers
rank_bm25
faiss-cpu
torch
```

- [ ] **Step 3: Create `.env.example`**

```
# LLM Provider: "ollama" or "gemini"
LLM_PROVIDER=ollama

# Ollama (used when LLM_PROVIDER=ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b

# Gemini (used when LLM_PROVIDER=gemini)
GEMINI_API_KEY=
GEMINI_MODEL=gemini-1.5-flash

# Embeddings — always local via sentence-transformers
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CROSS_ENCODER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2

# RAG defaults (each can be overridden per-request in POST /query)
RAG_MODE=hybrid
TOP_K=3
SEMANTIC_WEIGHT=0.7
LEXICAL_WEIGHT=0.3
ENABLE_RERANK=true
CONFIDENCE_THRESHOLD=0.5

# Cache dir for FAISS + BM25 index persistence
CACHE_DIR=cache
```

- [ ] **Step 4: Verify config validates correctly**

```bash
python - <<'EOF'
import os; os.environ["LLM_PROVIDER"] = "ollama"
from src.core.config import Config
Config.validate()
print("OK")
EOF
# Expected: OK
```

- [ ] **Step 5: Commit**

```bash
git add src/core/config.py requirements.txt .env.example
git commit -m "feat: rewrite config with LLM provider + RAG mode env vars"
```

---

### Task 3: LLM factory

**Files:**
- Create: `src/llm/__init__.py`
- Create: `src/llm/factory.py`

**Interfaces:**
- Consumes: `Config.LLM_PROVIDER`, `Config.GEMINI_API_KEY`, `Config.GEMINI_MODEL`, `Config.OLLAMA_BASE_URL`, `Config.OLLAMA_MODEL`
- Produces: `get_llm() -> BaseLanguageModel`

- [ ] **Step 1: Create `src/llm/__init__.py`** (empty)

```bash
touch src/llm/__init__.py
```

- [ ] **Step 2: Create `src/llm/factory.py`**

```python
from langchain_core.language_models import BaseLanguageModel
from src.core.config import Config


def get_llm() -> BaseLanguageModel:
    if Config.LLM_PROVIDER == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=Config.GEMINI_MODEL,
            google_api_key=Config.GEMINI_API_KEY,
            temperature=0.0,
        )
    from langchain_ollama import OllamaLLM
    return OllamaLLM(
        model=Config.OLLAMA_MODEL,
        base_url=Config.OLLAMA_BASE_URL,
        temperature=0.0,
    )
```

- [ ] **Step 3: Verify import**

```bash
python -c "from src.llm.factory import get_llm; print('OK')"
# Expected: OK
```

- [ ] **Step 4: Commit**

```bash
git add src/llm/
git commit -m "feat: add LLM factory — switches Gemini/Ollama from env"
```

---

### Task 4: Add `add_documents()` to HybridRetriever

**Files:**
- Modify: `src/domain/retrieval/retriever.py`

**Interfaces:**
- Consumes: existing `HybridRetriever.__init__(documents, rebuild_cache)`
- Produces: `HybridRetriever.add_documents(documents: List[Document]) -> None`

The microservice needs to accept documents via `/ingest` at any time after startup. FAISS supports incremental `add_documents`. BM25 has no incremental API so we rebuild it from the full corpus each time.

- [ ] **Step 1: Add `add_documents` method to `HybridRetriever`**

Open `src/domain/retrieval/retriever.py`. After the `lexical_search` method, add:

```python
def add_documents(self, documents: List[Document]) -> None:
    if not documents:
        return
    self.documents.extend(documents)
    if self.vectorstore is None:
        self._build_index()
    else:
        self.vectorstore.add_documents(documents)
        tokenized_corpus = [self._tokenize(doc.page_content) for doc in self.documents]
        self.bm25 = BM25Okapi(tokenized_corpus)
    self._save_cache()
```

- [ ] **Step 2: Smoke-test add_documents**

```bash
python - <<'EOF'
from langchain_core.documents import Document
from src.domain.retrieval.retriever import HybridRetriever
r = HybridRetriever(documents=[], rebuild_cache=True)
r.add_documents([Document(page_content="hello world", metadata={"id": "1"})])
results = r.semantic_search("hello", k=1)
assert len(results) == 1, f"Expected 1 result, got {len(results)}"
print("OK")
EOF
# Expected: OK
```

- [ ] **Step 3: Commit**

```bash
git add src/domain/retrieval/retriever.py
git commit -m "feat: add add_documents() to HybridRetriever for incremental ingest"
```

---

### Task 5: Refactor pipeline graph — inject LLM, remove benchmark code

**Files:**
- Modify: `src/pipeline/graph.py`

**Interfaces:**
- Consumes: `HybridRetriever`, `BaseLanguageModel` (injected, not imported directly)
- Produces: `build_rag_pipeline(retriever: HybridRetriever, llm: BaseLanguageModel) -> CompiledGraph`
- The `AgentState` TypedDict is unchanged except `config` no longer uses `skip_generation`

Changes:
1. Remove the global `_generator_llm` / `get_generator_llm()` function.
2. `generate_answer` receives `llm` via closure, not by importing Ollama directly.
3. Remove `skip_generation` handling (was benchmark-only).
4. `build_rag_pipeline` accepts a second parameter `llm`.

- [ ] **Step 1: Rewrite `src/pipeline/graph.py`**

```python
from typing import List, Tuple, Dict, Any, TypedDict
from concurrent.futures import ThreadPoolExecutor
from langchain_core.documents import Document
from langchain_core.language_models import BaseLanguageModel
from langgraph.graph import StateGraph, END

from src.core.config import Config
from src.domain.retrieval.retriever import HybridRetriever
from src.domain.reranking.cross_encoder import Reranker


def _normalize(scores: List[float]) -> List[float]:
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return [1.0] * len(scores) if hi > 0 else [0.0] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]


class AgentState(TypedDict):
    query: str
    documents: List[Document]
    semantic_results: List[Tuple[Document, float]]
    lexical_results: List[Tuple[Document, float]]
    merged_results: List[Tuple[Document, float]]
    confidence: float
    answer: str
    trace: List[str]
    config: Dict[str, Any]


def _retrieve(state: AgentState, retriever: HybridRetriever) -> AgentState:
    query = state["query"]
    mode = state.get("config", {}).get("mode", Config.RAG_MODE)
    sem, lex = [], []
    if mode == "semantic":
        sem = retriever.semantic_search(query)
    elif mode == "lexical":
        lex = retriever.lexical_search(query)
    else:
        with ThreadPoolExecutor(max_workers=2) as ex:
            fs = ex.submit(retriever.semantic_search, query)
            fl = ex.submit(retriever.lexical_search, query)
            sem, lex = fs.result(), fl.result()
    return {
        "semantic_results": sem,
        "lexical_results": lex,
        "trace": state.get("trace", []) + [f"Retrieve({mode})"],
    }


def _merge(state: AgentState) -> AgentState:
    cfg = state.get("config", {})
    sem_w = cfg.get("semantic_weight", Config.SEMANTIC_WEIGHT)
    lex_w = cfg.get("lexical_weight", Config.LEXICAL_WEIGHT)
    top_k = cfg.get("top_k", Config.TOP_K)

    doc_map: Dict[str, Dict] = {}
    sem = state["semantic_results"]
    lex = state["lexical_results"]

    if sem:
        norm = _normalize([s for _, s in sem])
        for i, (doc, raw) in enumerate(sem):
            did = doc.metadata.get("id", str(i))
            doc_map.setdefault(did, {"doc": doc, "sem": 0.0, "lex": 0.0, "raw_sem": 0.0})
            doc_map[did]["sem"] = norm[i]
            doc_map[did]["raw_sem"] = raw

    if lex:
        norm = _normalize([s for _, s in lex])
        for i, (doc, _) in enumerate(lex):
            did = doc.metadata.get("id", str(i))
            doc_map.setdefault(did, {"doc": doc, "sem": 0.0, "lex": 0.0, "raw_sem": 0.0})
            doc_map[did]["lex"] = norm[i]

    merged = []
    for entry in doc_map.values():
        score = sem_w * entry["sem"] + lex_w * entry["lex"]
        entry["doc"].metadata["merged_score"] = score
        entry["doc"].metadata["semantic_score"] = entry["raw_sem"]
        merged.append((entry["doc"], score))

    merged.sort(key=lambda x: x[1], reverse=True)
    candidates = merged[: top_k * 5]
    confidence = candidates[0][0].metadata.get("semantic_score", 0.0) if candidates else 0.0

    return {
        "merged_results": candidates,
        "confidence": confidence,
        "trace": state.get("trace", []) + ["Merge"],
    }


def _route(state: AgentState) -> str:
    enable = state.get("config", {}).get("enable_rerank", Config.ENABLE_RERANK)
    return "rerank" if enable else "generate"


def _rerank(state: AgentState) -> AgentState:
    cfg = state.get("config", {})
    top_k = cfg.get("top_k", Config.TOP_K)
    query = state["query"]
    docs = [d for d, _ in state["merged_results"]]
    if not docs:
        return {"documents": [], "trace": state.get("trace", []) + ["Rerank(empty)"]}
    reranker = Reranker.get_instance()
    if reranker.model:
        reranked = reranker.rerank(query, docs, top_k=top_k)
        final = [d for d, _ in reranked]
        tag = "Rerank(CrossEncoder)"
    else:
        final = docs[:top_k]
        tag = "Rerank(fallback)"
    return {"documents": final, "trace": state.get("trace", []) + [tag]}


def _make_generate(llm: BaseLanguageModel):
    def generate(state: AgentState) -> AgentState:
        cfg = state.get("config", {})
        top_k = cfg.get("top_k", Config.TOP_K)
        docs = state.get("documents") or [d for d, _ in state["merged_results"]][:top_k]
        context = "\n\n".join(
            f"[Source {d.metadata.get('id', '?')}] {d.page_content}" for d in docs
        )
        prompt = (
            "Answer the question based ONLY on the context below.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {state['query']}\n\nAnswer:"
        )
        try:
            answer = llm.invoke(prompt)
            if hasattr(answer, "content"):
                answer = answer.content
        except Exception as exc:
            answer = f"(LLM error: {exc})"
        return {"answer": str(answer), "trace": state.get("trace", []) + ["Generate"]}
    return generate


def build_rag_pipeline(retriever: HybridRetriever, llm: BaseLanguageModel):
    wf = StateGraph(AgentState)
    wf.add_node("retrieve", lambda s: _retrieve(s, retriever))
    wf.add_node("merge", _merge)
    wf.add_node("rerank", _rerank)
    wf.add_node("generate", _make_generate(llm))
    wf.set_entry_point("retrieve")
    wf.add_edge("retrieve", "merge")
    wf.add_conditional_edges("merge", _route, {"rerank": "rerank", "generate": "generate"})
    wf.add_edge("rerank", "generate")
    wf.add_edge("generate", END)
    return wf.compile()
```

- [ ] **Step 2: Verify the graph compiles**

```bash
python - <<'EOF'
from unittest.mock import MagicMock
from src.pipeline.graph import build_rag_pipeline
retriever = MagicMock()
llm = MagicMock()
pipeline = build_rag_pipeline(retriever, llm)
print("OK")
EOF
# Expected: OK
```

- [ ] **Step 3: Commit**

```bash
git add src/pipeline/graph.py
git commit -m "refactor: inject LLM into pipeline, remove all benchmark artifacts"
```

---

### Task 6: FastAPI app scaffolding — schemas + lifespan

**Files:**
- Create: `src/api/__init__.py`
- Create: `src/api/routes/__init__.py`
- Create: `src/api/schemas.py`
- Create: `src/api/app.py`

**Interfaces:**
- Produces:
  - `IngestRequest(documents: List[DocumentIn])` / `IngestResponse(indexed: int)`
  - `QueryRequest(query, mode?, top_k?, enable_rerank?, semantic_weight?, lexical_weight?)` / `QueryResponse(answer, sources, trace)`
  - `SourceDoc(id, content, score)`
  - `app` — FastAPI instance with `app.state.retriever` and `app.state.llm` set at startup

- [ ] **Step 1: Create `src/api/__init__.py` and `src/api/routes/__init__.py`**

```bash
touch src/api/__init__.py src/api/routes/__init__.py
```

- [ ] **Step 2: Create `src/api/schemas.py`**

```python
from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel


class DocumentIn(BaseModel):
    id: str
    content: str
    metadata: dict = {}


class IngestRequest(BaseModel):
    documents: List[DocumentIn]


class IngestResponse(BaseModel):
    indexed: int


class QueryRequest(BaseModel):
    query: str
    mode: Optional[Literal["hybrid", "semantic", "lexical"]] = None
    top_k: Optional[int] = None
    enable_rerank: Optional[bool] = None
    semantic_weight: Optional[float] = None
    lexical_weight: Optional[float] = None


class SourceDoc(BaseModel):
    id: str
    content: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceDoc]
    trace: List[str]
```

- [ ] **Step 3: Create `src/api/app.py`**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.core.config import Config
from src.domain.retrieval.retriever import HybridRetriever
from src.llm.factory import get_llm
from src.api.routes import ingest, query as query_route


@asynccontextmanager
async def lifespan(app: FastAPI):
    Config.validate()
    app.state.retriever = HybridRetriever(documents=[], rebuild_cache=False)
    app.state.llm = get_llm()
    yield


app = FastAPI(title="RAG Microservice", version="1.0.0", lifespan=lifespan)
app.include_router(ingest.router)
app.include_router(query_route.router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "llm_provider": Config.LLM_PROVIDER,
        "rag_mode": Config.RAG_MODE,
    }
```

- [ ] **Step 4: Verify app imports**

```bash
python -c "from src.api.app import app; print('OK')"
# Expected: OK  (will fail at Task 7/8 if routes don't exist yet — that's fine)
```

- [ ] **Step 5: Commit**

```bash
git add src/api/
git commit -m "feat: FastAPI app scaffolding — schemas + lifespan startup"
```

---

### Task 7: Implement /ingest route

**Files:**
- Create: `src/api/routes/ingest.py`

**Interfaces:**
- Consumes: `app.state.retriever: HybridRetriever`, `IngestRequest`, `IngestResponse`
- Produces: `POST /ingest` → `IngestResponse`

- [ ] **Step 1: Create `src/api/routes/ingest.py`**

```python
from fastapi import APIRouter, Request
from langchain_core.documents import Document

from src.api.schemas import IngestRequest, IngestResponse

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse)
def ingest(body: IngestRequest, request: Request) -> IngestResponse:
    retriever = request.app.state.retriever
    docs = [
        Document(page_content=d.content, metadata={"id": d.id, **d.metadata})
        for d in body.documents
    ]
    retriever.add_documents(docs)
    return IngestResponse(indexed=len(docs))
```

- [ ] **Step 2: Smoke-test via curl (start server first)**

```bash
uvicorn src.api.app:app --port 8000 &
sleep 3
curl -s -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"documents":[{"id":"doc1","content":"The sky is blue."}]}' | python -m json.tool
# Expected: {"indexed": 1}
kill %1
```

- [ ] **Step 3: Commit**

```bash
git add src/api/routes/ingest.py
git commit -m "feat: POST /ingest — adds documents to FAISS+BM25 index"
```

---

### Task 8: Implement /query route

**Files:**
- Create: `src/api/routes/query.py`

**Interfaces:**
- Consumes: `app.state.retriever`, `app.state.llm`, `QueryRequest`, `build_rag_pipeline`
- Produces: `POST /query` → `QueryResponse`

- [ ] **Step 1: Create `src/api/routes/query.py`**

```python
from fastapi import APIRouter, Request

from src.api.schemas import QueryRequest, QueryResponse, SourceDoc
from src.core.config import Config
from src.pipeline.graph import build_rag_pipeline, AgentState

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
def query(body: QueryRequest, request: Request) -> QueryResponse:
    retriever = request.app.state.retriever
    llm = request.app.state.llm
    pipeline = build_rag_pipeline(retriever, llm)

    run_cfg = {
        "mode": body.mode or Config.RAG_MODE,
        "top_k": body.top_k or Config.TOP_K,
        "enable_rerank": body.enable_rerank if body.enable_rerank is not None else Config.ENABLE_RERANK,
        "semantic_weight": body.semantic_weight or Config.SEMANTIC_WEIGHT,
        "lexical_weight": body.lexical_weight or Config.LEXICAL_WEIGHT,
    }

    state: AgentState = {
        "query": body.query,
        "documents": [],
        "semantic_results": [],
        "lexical_results": [],
        "merged_results": [],
        "confidence": 0.0,
        "answer": "",
        "trace": [],
        "config": run_cfg,
    }

    result = pipeline.invoke(state)

    sources = [
        SourceDoc(
            id=d.metadata.get("id", ""),
            content=d.page_content,
            score=d.metadata.get("merged_score", 0.0),
        )
        for d in (result.get("documents") or [])
    ]

    return QueryResponse(
        answer=result.get("answer", ""),
        sources=sources,
        trace=result.get("trace", []),
    )
```

- [ ] **Step 2: End-to-end smoke test (requires Ollama or Gemini available)**

```bash
# Assuming Ollama is running with qwen2.5:3b
uvicorn src.api.app:app --port 8000 &
sleep 3

# Ingest a document
curl -s -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"documents":[{"id":"doc1","content":"The capital of France is Paris."}]}'

# Query it
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the capital of France?","mode":"hybrid"}' | python -m json.tool
# Expected: JSON with "answer" containing "Paris", "sources" with doc1, "trace" showing steps

kill %1
```

- [ ] **Step 3: Commit**

```bash
git add src/api/routes/query.py
git commit -m "feat: POST /query — runs configurable RAG pipeline, returns answer + sources"
```

---

### Task 9: Dockerfile + README

**Files:**
- Create: `Dockerfile`
- Create: `README.md`

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create `README.md`**

```markdown
# RAG Microservice

Configurable Hybrid/Semantic/Lexical RAG microservice. Switch between Gemini and Ollama via `.env`.

## Quickstart

```bash
cp .env.example .env   # edit LLM_PROVIDER, keys, etc.
pip install -r requirements.txt
uvicorn src.api.app:app --reload
```

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Status + active LLM provider |
| POST | /ingest | Add documents to the index |
| POST | /query | Run RAG and return answer + sources |

### POST /ingest
```json
{ "documents": [{ "id": "doc1", "content": "..." }] }
```

### POST /query
```json
{
  "query": "What is X?",
  "mode": "hybrid",
  "top_k": 3,
  "enable_rerank": true,
  "semantic_weight": 0.7,
  "lexical_weight": 0.3
}
```
All fields except `query` are optional — defaults come from `.env`.

## Docker

```bash
docker build -t rag-ms .
docker run -p 8000:8000 --env-file .env rag-ms
```
```

- [ ] **Step 3: Build and verify Docker image**

```bash
docker build -t rag-ms .
# Expected: Successfully built ...
```

- [ ] **Step 4: Commit**

```bash
git add Dockerfile README.md
git commit -m "feat: Dockerfile + README for RAG microservice"
```

---

## Self-Review Checklist

- [x] Research files deleted (Task 1)
- [x] Configurable LLM: Gemini / Ollama via `LLM_PROVIDER` env (Tasks 2, 3)
- [x] Configurable RAG mode: hybrid / semantic / lexical — default from env, overridable per-request (Tasks 2, 5, 8)
- [x] `/ingest` endpoint for adding documents (Tasks 4, 7)
- [x] `/query` endpoint returning answer + sources + trace (Tasks 5, 8)
- [x] No benchmark/evaluation code anywhere
- [x] Old Cursor plan file deleted (Task 1, Step 4)
- [x] Docker-ready (Task 9)
