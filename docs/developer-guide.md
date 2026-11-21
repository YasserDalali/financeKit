<!-- Moved word for word from the old README.md (master, 1d72794). Only the relative link paths changed, so they work from docs/. It describes the three services on master, not the Java modular monolith. -->

# FinanceKit

A collection of financial microservices for portfolio risk and sector valuation.

| Service | Stack | Default port | OpenAPI |
|---------|-------|--------------|---------|
| [risk-management-ms](../risk-management-ms/) | Spring Boot 3, SQL Server | **8080** (host) / **18080** (Docker) | [`openapi.json`](../risk-management-ms/openapi.json) |
| [sector-valuation-ms](../sector-valuation-ms/) | Node.js, Express, Redis | **3000** | — |

Central copies of the API specs live in [`docs/openapi/`](./openapi/).

---

## Prerequisites

| Tool | Used by |
|------|---------|
| Docker + Docker Compose | FinRisk (SQL Server + API container) |
| JDK 21 + Maven 3.9+ | FinRisk (local JVM / tests) |
| Node.js 20+ | Sector valuation |
| Redis | Sector valuation (peer-data cache) |

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

More detail: [`risk-management-ms/README.md`](../risk-management-ms/README.md)

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

# Sector valuation
cd sector-valuation-ms && npm test
```

---

## Project layout

```
financeKit/
├── docs/openapi/           # OpenAPI JSON exports
├── risk-management-ms/     # FinRisk portfolio API
└── sector-valuation-ms/    # Sector peer / DCF API
```

Each service is independently deployable. They share the FMP API key pattern but do not call each other at runtime.
