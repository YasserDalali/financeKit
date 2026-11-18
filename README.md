# FinanceKit

A collection of financial microservices for portfolio risk, sector valuation, and document Q&A.

| Service | Stack | Default port | OpenAPI |
|---------|-------|--------------|---------|
| [risk-management-ms](./risk-management-ms/) | Spring Boot 3, SQL Server | **8080** (host) / **18080** (Docker) | [`openapi.json`](./risk-management-ms/openapi.json) |
| [hybrid-rag](./hybrid-rag/) | FastAPI, LangChain, FAISS | **8000** | [`openapi.json`](./hybrid-rag/openapi.json) |
| [sector-valuation-ms](./sector-valuation-ms/) | Node.js, Express, Redis | **3000** | — |

Central copies of the API specs live in [`docs/openapi/`](./docs/openapi/).

---

## Prerequisites

| Tool | Used by |
|------|---------|
| Docker + Docker Compose | FinRisk (SQL Server + API container) |
| JDK 21 + Maven 3.9+ | FinRisk (local JVM / tests) |
| Python 3.11+ | Hybrid RAG |
| Node.js 20+ | Sector valuation |
| Redis | Sector valuation (peer-data cache) |
| Ollama (optional) | Hybrid RAG when `LLM_PROVIDER=ollama` |

---

## Development

### FinRisk API (`risk-management-ms`)

Investment portfolio API: users, accounts, assets, trades, holdings, P&L, risk score, beta, sector exposure, and diversification.

**1. Configure environment**

```bash
cd risk-management-ms
cp .env.example .env
# Edit .env — set SA_PASSWORD (strong password) and optional FMP_API_KEY
set -a && source .env && set +a
```

**2. Start SQL Server + API (recommended)**

```bash
make up
# Equivalent: docker compose up -d --build
```

The API is exposed on **http://localhost:18080** (host port mapped from container `:8080`).

**3. Run migrations and seed (first time or after wiping the DB volume)**

```bash
bash db/scripts/apply-migrations.sh FinRiskDB
bash db/scripts/seed.sh FinRiskDB
```

**4. Verify**

```bash
curl -sf http://localhost:18080/actuator/health
curl -sf "http://localhost:18080/api/v1/users?page=0&size=2"
```

**Alternative: SQL Server in Docker, API on the host**

```bash
make dev          # starts sqlserver only
mvn spring-boot:run   # API on http://localhost:8080
```

Stop the `risk-management-api` container first if port 8080 is already taken.

**Makefile shortcuts**

```bash
make dev     # SQL Server only
make up      # SQL Server + API (:18080)
make test    # mvn test
make verify  # mvn test + integration tests
make e2e     # full e2e script (migrations, tests, Docker, happy-path)
```

More detail: [`risk-management-ms/README.md`](./risk-management-ms/README.md)

---

### Hybrid RAG (`hybrid-rag`)

Document ingestion and question-answering with hybrid (BM25 + semantic), semantic-only, or lexical-only retrieval. Supports Ollama or Gemini as the LLM.

**1. Configure environment**

```bash
cd hybrid-rag
cp .env.example .env
# Set LLM_PROVIDER=ollama or gemini; add GEMINI_API_KEY if using Gemini
```

**2. Install and run**

```bash
pip install -r requirements.txt

# If using Ollama locally:
# ollama pull qwen2.5:3b

uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

**3. Verify**

```bash
curl -sf http://localhost:8000/health
```

Interactive docs: **http://localhost:8000/docs**

More detail: [`hybrid-rag/README.md`](./hybrid-rag/README.md)

---

### Sector Valuation (`sector-valuation-ms`)

Peer comparison, DCF valuation, and combined analyze/compare endpoints backed by FinancialModelingPrep (FMP) and Redis caching.

**1. Start Redis**

```bash
docker run -d --name sector-redis -p 6379:6379 redis:7-alpine
```

**2. Configure environment**

```bash
cd sector-valuation-ms
cp .env.example .env
# Set FMP_API_KEY (required for live market data)
```

**3. Install and run**

```bash
npm install
npm run dev    # hot reload via node --watch
# or: npm start
```

**4. Verify**

```bash
curl -sf http://localhost:3000/health
```

---

## Production build and deploy

### FinRisk API

**Build the JAR and Docker image**

```bash
cd risk-management-ms
set -a && source .env && set +a

mvn -B -DskipTests package
docker compose build risk-management-api
```

**Run the stack**

```bash
docker compose up -d
```

Set production values in `.env`:

- `SA_PASSWORD` — SQL Server SA password
- `FMP_API_KEY` — market data sync (optional but needed for price sync endpoints)

Apply migrations against the production database before serving traffic:

```bash
bash db/scripts/apply-migrations.sh FinRiskDB
```

The container listens on **8080** internally; map it with `ports` in `docker-compose.yml` (default host mapping **18080**).

---

### Hybrid RAG

**Build and run**

```bash
cd hybrid-rag
docker build -t financekit-hybrid-rag .
docker run -d \
  --name hybrid-rag \
  -p 8000:8000 \
  --env-file .env \
  -v hybrid-rag-cache:/app/cache \
  financekit-hybrid-rag
```

Mount a volume on `CACHE_DIR` (default `cache/`) so FAISS and BM25 indexes survive restarts.

For Gemini in production, set `LLM_PROVIDER=gemini` and `GEMINI_API_KEY`. For Ollama, point `OLLAMA_BASE_URL` at your Ollama host.

---

### Sector Valuation

No Dockerfile is included. Deploy as a standard Node.js service:

```bash
cd sector-valuation-ms
npm ci --omit=dev
export FMP_API_KEY=...
export REDIS_URL=redis://your-redis-host:6379
export PORT=3000
node src/server.js
```

Run behind a reverse proxy (nginx, ALB, etc.) and use a managed Redis instance for the peer cache.

---

## How to use

### FinRisk — typical workflow

All endpoints are under `/api/v1`. Currency is always USD. No authentication is enforced in this project.

```bash
BASE=http://localhost:18080/api/v1

# 1. Create a user
curl -s -X POST "$BASE/users" \
  -H 'Content-Type: application/json' \
  -d '{"fullName":"Jane Doe","email":"jane@example.com"}'

# 2. Create an investment account
curl -s -X POST "$BASE/accounts" \
  -H 'Content-Type: application/json' \
  -d '{"userId":1,"accountName":"Growth","initialDeposit":10000}'

# 3. List assets and buy
curl -s "$BASE/assets?symbol=AAPL"
curl -s -X POST "$BASE/transactions/buy" \
  -H 'Content-Type: application/json' \
  -d '{"accountId":1,"assetId":1,"quantity":10,"unitPrice":150}'

# 4. Portfolio analytics
curl -s "$BASE/accounts/1/portfolio"
curl -s "$BASE/accounts/1/profit-loss"
curl -s "$BASE/accounts/1/risk"
curl -s "$BASE/accounts/1/beta"
curl -s "$BASE/accounts/1/sector-exposure"
curl -s "$BASE/accounts/1/diversification"
```

After seeding (`bash db/scripts/seed.sh FinRiskDB`), account **1** has sample holdings you can query immediately.

Postman collections: `risk-management-ms/postman/`

---

### Hybrid RAG — ingest then query

```bash
BASE=http://localhost:8000

# Ingest documents
curl -s -X POST "$BASE/ingest" \
  -H 'Content-Type: application/json' \
  -d '{
    "documents": [
      {
        "page_content": "Apple reported record revenue in Q4 driven by iPhone sales.",
        "metadata": {"source": "earnings_call", "ticker": "AAPL"}
      }
    ]
  }'

# Ask a question
curl -s -X POST "$BASE/query" \
  -H 'Content-Type: application/json' \
  -d '{"question": "What drove Apple revenue?"}'
```

Response includes `answer`, `sources` (retrieved chunks), and `trace` (pipeline steps).

Configure retrieval via `.env`: `RAG_MODE` (`hybrid` | `semantic` | `lexical`), `TOP_K`, weights, and reranking.

---

### Sector Valuation — analyze a metric vs peers

```bash
BASE=http://localhost:3000

# Compare a ticker's P/E to sector peers
curl -s -X POST "$BASE/api/analyze" \
  -H 'Content-Type: application/json' \
  -d '{"ticker":"AAPL","metric":"PE"}'

# DCF valuation (fcf/shares optional — fetched from FMP when omitted)
curl -s -X POST "$BASE/api/dcf" \
  -H 'Content-Type: application/json' \
  -d '{
    "ticker": "AAPL",
    "discountRate": 0.10,
    "terminalGrowthRate": 0.03,
    "projectionYears": 10
  }'

# Combined peer + DCF comparison
curl -s -X POST "$BASE/api/compare" \
  -H 'Content-Type: application/json' \
  -d '{
    "ticker": "AAPL",
    "metric": "PE",
    "discountRate": 0.10,
    "terminalGrowthRate": 0.03
  }'
```

Supported metrics: `PE`, `PB`, `EV_EBITDA`, `PS`.

---

## Testing

```bash
# FinRisk
cd risk-management-ms && mvn test

# Hybrid RAG
cd hybrid-rag && pytest

# Sector valuation
cd sector-valuation-ms && npm test
```

---

## Project layout

```
financeKit/
├── docs/openapi/           # OpenAPI JSON exports
├── risk-management-ms/     # FinRisk portfolio API
├── hybrid-rag/             # RAG microservice
└── sector-valuation-ms/    # Sector peer / DCF API
```

Each service is independently deployable. They share the FMP API key pattern but do not call each other at runtime.
