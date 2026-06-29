# FinanceKit Microservice Redesign
**Date:** 2026-06-28

## Scope

Two independent microservice changes:

1. **hybrid-rag** — wrap the existing Python RAG pipeline in a gRPC microservice with configurable retrieval mode and switchable LLM backend.
2. **volatility-ms** — remove the React frontend, connect to Yahoo Finance for live stock/ETF prices, add an SSE endpoint that streams price ticks and portfolio snapshots.

---

## 1. hybrid-rag gRPC Microservice

### 1.1 Overview

The existing LangGraph pipeline (FAISS semantic search + BM25 lexical search + cross-encoder reranker) is wrapped in a Python gRPC server. The corpus is financial statements loaded from a `documents/` directory at startup. The index is cached to disk; rebuilding requires a restart. No runtime ingestion.

The git remote is removed (`git remote remove origin`) to make the repo standalone.

### 1.2 Proto Contract

File: `proto/rag.proto`

```protobuf
syntax = "proto3";
package rag;

enum Mode {
  HYBRID   = 0;
  LEXICAL  = 1;
  SEMANTIC = 2;
}

enum LlmBackend {
  OLLAMA = 0;
  GEMINI = 1;
}

message QueryRequest {
  string     query          = 1;
  Mode       mode           = 2;  // overrides config default if set
  LlmBackend llm_backend    = 3;  // overrides config default if set
  float      semantic_weight = 4; // 0 = use config default
  bool       enable_rerank  = 5;
  int32      top_k          = 6;  // 0 = use config default
}

message Chunk {
  string content = 1;
  string source  = 2;  // filename the chunk came from
  float  score   = 3;
}

message QueryResponse {
  string          answer     = 1;
  repeated Chunk  chunks     = 2;
  repeated string trace      = 3;
  float           confidence = 4;
}

service RagService {
  rpc Query(QueryRequest) returns (QueryResponse);
}
```

### 1.3 Configuration

File: `config.yaml` (repo root)

```yaml
server:
  port: 50051

documents:
  path: "./documents"          # drop .txt or .pdf financial statements here

index:
  cache_dir: "./cache"
  rebuild_on_start: false      # set true to force index rebuild

retrieval:
  default_mode: hybrid         # hybrid | lexical | semantic
  semantic_weight: 0.7
  lexical_weight: 0.3
  top_k: 3
  enable_rerank: true

llm:
  default_backend: ollama      # ollama | gemini
  ollama:
    base_url: "http://localhost:11434"
    model: "qwen2.5:3b"
  gemini:
    api_key: "${GEMINI_API_KEY}"
    model: "gemini-2.5-flash"
```

`GEMINI_API_KEY` is read from the environment (`.env` file or injected at deploy time). It is never committed.

### 1.4 File Layout

```
hybrid-rag/
├── proto/
│   └── rag.proto
├── src/
│   ├── core/
│   │   └── config.py          # updated: loads from config.yaml instead of hardcoded values
│   ├── domain/                # unchanged
│   ├── pipeline/              # unchanged
│   ├── llm/
│   │   └── backend.py         # NEW: OllamaBackend + GeminiBackend, both expose generate(prompt) -> str
│   └── server.py              # NEW: gRPC servicer + server startup
├── documents/                 # NEW: financial statements go here (.txt, .pdf)
├── config.yaml                # NEW
├── requirements.txt           # + grpcio, grpcio-tools, google-generativeai, pyyaml, pypdf
└── Dockerfile                 # NEW
```

### 1.5 LLM Backend Abstraction

`src/llm/backend.py` defines:

- `LlmBackend` abstract base: `generate(prompt: str) -> str`
- `OllamaBackend`: wraps existing `OllamaLLM` from `langchain_ollama`
- `GeminiBackend`: uses `google.generativeai` SDK with the configured model
- `get_backend(config) -> LlmBackend`: factory that reads `llm.default_backend` from config, returns the appropriate instance

The existing `generate_answer` node in `pipeline/graph.py` is updated to call `backend.generate(prompt)` instead of instantiating `OllamaLLM` directly.

### 1.6 Server Startup Sequence

1. Load `config.yaml`
2. Scan `documents/` — load `.txt` files directly, parse `.pdf` files with `pypdf`
3. Build or load cached FAISS + BM25 index via existing `HybridRetriever`
4. Compile the LangGraph pipeline via existing `build_rag_pipeline()`
5. Start gRPC server on configured port
6. On `QueryRequest`: map proto fields → pipeline `config` dict → run pipeline → map result to `QueryResponse`

### 1.7 Git Remote Removal

```bash
cd hybrid-rag && git remote remove origin
```

Local history is preserved. No upstream link.

### 1.8 Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python -m grpc_tools.protoc -I proto --python_out=src/generated --grpc_python_out=src/generated proto/rag.proto
EXPOSE 50051
CMD ["python", "src/server.py"]
```

---

## 2. volatility-ms — Yahoo Finance + SSE

### 2.1 Overview

The React frontend (`finrisk-web/`) is deleted. In its place, a `GET /api/v1/stream/market` SSE endpoint streams two event types: `price_tick` (per-symbol price updates) and `portfolio_snapshot` (per-account total value + risk score). Prices for `STOCK` and `ETF` assets are fetched from Yahoo Finance on a configurable polling interval.

### 2.2 Yahoo Finance Integration

**Client:** `YahooFinanceClient` is a Spring `@Component` using `RestTemplate`. It calls:

```
GET https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d
```

Parses the JSON response to extract the most recent closing price. Returns `Optional<BigDecimal>` — empty on any error (network, parse, symbol not found).

**Scheduler:** `PriceRefreshScheduler` is annotated `@Component` with `@EnableScheduling`. It runs on a fixed delay (default 30 s, configurable via `app.price-refresh-interval-ms` in `application.yml`).

Each cycle:
1. Query DB for all assets where `type IN ('STOCK', 'ETF')`
2. For each asset, call `YahooFinanceClient.fetchPrice(symbol)`
3. On success, call existing `AssetService.updatePrice()` — writes to `assets` and `asset_price_history` tables (no schema change)
4. Collect updated `(symbol, price, timestamp)` tuples
5. Broadcast `price_tick` SSE events via `SseEmitterRegistry`
6. For each account with active SSE connections, call existing `RiskService.computeRisk(accountId)` and broadcast `portfolio_snapshot`

### 2.3 SSE Endpoint

**Controller:** `MarketStreamController` at `/api/v1/stream/market`

```
GET /api/v1/stream/market?accountId={id}
```

- Returns `text/event-stream`
- Creates an `SseEmitter` with a configurable timeout (default 5 min)
- Registers it in `SseEmitterRegistry` under the given `accountId`
- On emitter completion/timeout/error, removes it from the registry

**Event format:**

```
event: price_tick
data: {"symbol":"AAPL","price":213.45,"currency":"USD","timestamp":"2026-06-28T14:30:00Z"}

event: portfolio_snapshot
data: {"accountId":1,"totalValue":48200.00,"riskScore":34.2,"riskLevel":"MEDIUM"}
```

**Registry:** `SseEmitterRegistry` is a `@Component` holding a `ConcurrentHashMap<Long, CopyOnWriteArrayList<SseEmitter>>` (keyed by `accountId`). Exposes:
- `register(accountId, emitter)`
- `remove(accountId, emitter)`
- `broadcastPriceTick(events)` — sends to all connected emitters regardless of accountId
- `broadcastPortfolioSnapshot(accountId, snapshot)` — sends only to emitters for that account

### 2.4 Frontend & Docker Removal

- Delete `finrisk-web/` directory entirely
- Remove `finrisk-web` service block from `docker-compose.yml`
- Remove `finrisk-web/src` from `sonar.sources` in `pom.xml`
- Remove `finrisk-web/src/generated/**` from `sonar.exclusions` in `pom.xml`

### 2.5 New Files

```
src/main/java/com/finrisk/
├── client/
│   └── YahooFinanceClient.java       # RestTemplate-based Yahoo Finance v8 client
├── scheduler/
│   └── PriceRefreshScheduler.java    # @Scheduled price polling + SSE broadcast
└── sse/
    ├── SseEmitterRegistry.java        # Thread-safe emitter store
    └── MarketStreamController.java    # GET /api/v1/stream/market
```

`application.yml` additions:
```yaml
app:
  price-refresh-interval-ms: 30000
  sse-timeout-ms: 300000
```

---

## Error Handling

**hybrid-rag:** gRPC status codes — `INVALID_ARGUMENT` for bad mode/backend values, `INTERNAL` for index failures, `UNAVAILABLE` if LLM backend is unreachable. Empty corpus returns `NOT_FOUND`.

**volatility-ms:** Yahoo Finance fetch failures are logged and skipped (price not updated for that symbol that cycle). SSE emitter errors remove the emitter from the registry silently. `accountId` not found on SSE connect returns HTTP 404 before upgrading to stream.

## Testing

**hybrid-rag:** Python `pytest` + `grpc.experimental.aio` test channel. One test per mode (lexical, semantic, hybrid), one per LLM backend (mocked). Index built from a small fixture corpus of 3 financial statement excerpts.

**volatility-ms:** Existing test structure (REST-assured ITs, JUnit unit tests). New tests: `YahooFinanceClientTest` mocks HTTP with `MockRestServiceServer`. `PriceRefreshSchedulerTest` mocks `YahooFinanceClient` and asserts `AssetService.updatePrice` is called. `MarketStreamControllerIT` connects to the SSE endpoint and asserts event types are received.
