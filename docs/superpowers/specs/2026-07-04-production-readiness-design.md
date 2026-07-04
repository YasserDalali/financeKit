# FinanceKit Production Readiness
**Date:** 2026-07-04
**Status:** Approved

## Goal

Bring all three financeKit services (risk-management-ms, sector-valuation-ms, hybrid-rag) to production quality: fix correctness and reliability bugs, harden deployment, and close config/doc gaps. Depth is "must-fix plus key hygiene" — not a full observability or auth build-out.

## Decisions (user-confirmed)

- **Scope:** all three services plus cross-cutting repo work.
- **Auth:** stays out — services deploy behind a trusted gateway/VPN; the README keeps documenting this assumption.
- **Packaging:** per-service Docker images plus a root `docker-compose.yml` that runs the whole kit.
- **Execution:** service-by-service, hardest first: risk-management-ms → sector-valuation-ms → hybrid-rag → cross-cutting. Each service's test suite is green before moving to the next.

## 1. risk-management-ms

### 1.1 Deposit/withdraw race condition (critical)

`AccountService.deposit/withdraw` (`src/main/java/com/finrisk/service/AccountService.java:69-84`) does an unprotected read-modify-write; two concurrent $50 withdrawals on a $100 account can both succeed.

Fix: atomic conditional SQL in the DAO —

- Deposit: `UPDATE accounts SET cash_balance = cash_balance + ? WHERE id = ?`
- Withdraw: `UPDATE accounts SET cash_balance = cash_balance - ? WHERE id = ? AND cash_balance >= ?`

Zero rows affected on withdraw means insufficient funds (or missing account — disambiguate with a follow-up existence check) and maps to the existing error responses. The service re-reads the account for the response body after the update. A concurrency test (parallel withdrawals against one account) proves the invariant: balance never goes negative and total debits never exceed the starting balance.

### 1.2 FMP client hardening

`FmpMarketDataProvider` (`src/main/java/com/finrisk/marketdata/fmp/FmpMarketDataProvider.java`):

- `HttpClient` gets a connect timeout (5 s) and each request a request timeout (10 s).
- `catch (Exception)` blocks narrow to `IOException` / `InterruptedException` (restoring the interrupt flag) / JSON parse failures, each logged at WARN with the symbol and cause. Behavior on failure stays "return empty" so callers degrade as today, but failures become diagnosable.

### 1.3 N+1 elimination

- **Prices:** `AssetPriceHistoryDao` gains a batch method returning the latest N prices for a set of asset IDs in one query; `RiskService.computeRisk` and `BetaService.computeBeta` use it instead of per-holding queries.
- **Symbols:** `TransactionService.listForAccount` resolves symbols for the whole page in one query instead of one lookup per row.
- **FMP profiles:** `SectorExposureService` calls (one HTTP request per holding) go through an in-memory TTL cache (`ConcurrentHashMap`, 24 h TTL, single-instance deployment assumption). `DiversificationService` benefits transitively.

### 1.4 Error handling and logging

`GlobalExceptionHandler` logs the underlying exception (ERROR level with stack trace) before returning the generic `DaoException` / fallback bodies. Response shapes do not change.

### 1.5 Hygiene

- `application.yml`: `server.shutdown: graceful` + 30 s lifecycle timeout.
- Hikari (`config/DatabaseConnection.java`): explicit `connectionTimeout` (10 s) and `minimumIdle`.
- Risk-score divisor `0.12` (`RiskService.java:92`) becomes a documented config property `app.risk.volatility-baseline` (default 0.12, meaning: annualized volatility that maps to score 100).
- Dockerfile: non-root user, `-XX:MaxRAMPercentage=75`, `HEALTHCHECK` hitting `/actuator/health`.

### 1.6 New tests

- `TransactionService` buy/sell happy path + insufficient funds/holdings.
- `AccountService` deposit/withdraw incl. the concurrent-withdrawal test.
- `ProfitLossService` P&L math against seeded data.
- Batch-price DAO method IT.

## 2. sector-valuation-ms

### 2.1 Redis config mismatch (critical)

`src/app.js` reads `REDIS_HOST`/`REDIS_PORT`; `.env.example` and the README promise `REDIS_URL`. Fix: the client accepts `REDIS_URL` when set, falling back to host/port, and `.env.example` documents both (URL primary).

### 2.2 DCF null poisoning (critical)

When FMP returns null `fcf` or null/zero `sharesOutstanding`, `/api/dcf` and `/api/compare` currently compute NaN/Infinity. Fix: validate fetched fundamentals before computing; missing data returns 502 `UPSTREAM_DATA_UNAVAILABLE` with the offending field named.

### 2.3 Validation

Zod schemas gain: `terminalGrowthRate < discountRate` (refinement), bounds on rates (−0.5 to 0.5 for growth, 0.001 to 1 for discount), and the same bounds for stage rates.

### 2.4 Lifecycle and process safety

`src/server.js`: SIGTERM/SIGINT handlers close the HTTP server then the Redis client; `listen` failures are handled; `unhandledRejection`/`uncaughtException` log and exit non-zero.

### 2.5 Peer-data error semantics

Routes distinguish "all/most peer fetches failed" (502 upstream failure) from "peers fetched but too few with the metric" (422 insufficient data), instead of a generic 500.

### 2.6 Hygiene

- Axios timeout (10 s) on all FMP calls.
- `helmet` middleware.
- `PEER_LIMIT` and `CACHE_TTL_SECONDS` env vars are honored by the routes (currently hardcoded).
- **New** Dockerfile (node:20 slim variant, non-root, `HEALTHCHECK` on `/health`) + `.dockerignore`.
- Fix the Jest open-handle hang (close Redis/clients in teardown).

### 2.7 New tests

Null-FCF/zero-shares → 502; growth ≥ discount → 400; REDIS_URL parsing; graceful-shutdown unit-level check where feasible; peer-failure 502 vs 422.

## 3. hybrid-rag

### 3.1 Event-loop blocking (critical)

`src/api/routes/query.py` and `ingest.py` call the blocking pipeline/retriever inside `async def`. Fix: wrap the blocking work in `asyncio.to_thread(...)`. The LLM invocation gets a timeout (60 s) so a hung provider returns 504 instead of blocking forever.

### 3.2 Thread safety

`HybridRetriever.add_documents` mutates `documents`/`vectorstore`/`bm25` unguarded. Fix: an `RLock` owned by the retriever; mutation takes it, and query paths snapshot the references under it. A concurrency smoke test (parallel ingest + query) guards the invariant.

### 3.3 Error semantics

- LLM/pipeline exceptions stop being returned as `answer` text (`src/pipeline/graph.py:135-140`); they propagate to the route and map to 502 (provider error) / 504 (timeout).
- Request validation: empty `question` or empty `documents` → 422 (Pydantic validators).
- Ingest wraps retriever errors → structured 500 with a proper body.

### 3.4 Builds and deploy

- `requirements.txt` pinned to the exact versions in the working venv (`pip freeze` filtered to direct deps + their pins).
- Dockerfile: pinned patch-version base image, non-root user, `HEALTHCHECK` on `/health`; new `.dockerignore` excluding `venv/`, `.git/`, `cache/`, `__pycache__/`, `tests/`.
- FAISS `allow_dangerous_deserialization=True` stays (LangChain local load requires it); the README documents that the cache volume must be trusted/private.

### 3.5 Hygiene

`print` → `logging` module across `src/`; uvicorn/app log config so container logs are structured lines.

### 3.6 New tests

LLM failure → 502; LLM timeout → 504; empty question/documents → 422; parallel ingest+query smoke test.

## 4. Cross-cutting

- **Root `docker-compose.yml`** at the repo root: `risk-management-api` + `sqlserver` (reusing the service's existing compose definitions), `sector-valuation` + `redis`, `hybrid-rag` with a named cache volume. Healthcheck-based `depends_on` ordering. Ports: 18080 / 3000 / 8000 as today. Env via root `.env` (documented in `.env.example` at root).
- **README:** new "Run the whole kit" section; Redis env var docs updated; sector-valuation Docker instructions replace the "no Dockerfile" note.
- **`.claude/CLAUDE.md` rewrite:** replace the stale Cloudflare-microloans content with financeKit facts (three services, commands, test invocations, architecture pointers).
- **Commit hygiene:** commit `README.md` + `docs/openapi/` in the parent repo; commit pending work in each service repo (e.g. `openapi.yaml` in risk-management-ms, `openapi.json` in hybrid-rag); update parent gitlinks. Pushing to remotes is left to the user.

## Out of scope

Auth (gateway assumption documented), Kubernetes, rate limiting, metrics/request tracing, OpenAPI spec for sector-valuation-ms, incremental BM25 indexing (documented as a known scale limitation), FinRisk load testing.

## Testing & verification bar

- Every behavioral fix lands with a failing-first test (TDD).
- Each service's full suite passes before moving to the next service.
- Final verification: `docker compose up` at the root brings up all five containers healthy; smoke curls hit each service's happy path (FinRisk user→account→buy→risk, sector-valuation analyze+dcf with mocked-or-live FMP, hybrid-rag ingest→query with Ollama or a stubbed provider).
