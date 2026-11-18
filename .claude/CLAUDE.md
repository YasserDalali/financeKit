# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## TIER 1 — HARD RULES (check before every action)
- Never commit secrets.
- Never claim what unread code does — open and read files first.
- Before touching a file: is the task unambiguous AND trivial (<3 steps, 1 file)?
  If not → plan first.

## TIER 2 — WORKFLOW
- Plan mode for any non-trivial task (3+ steps or an architectural call).
- Write the plan to tasks/todo.md; check in before implementing.
- Use /ponytail during implementation and TDD.
- Use subagents liberally to keep the main context clean.

## TIER 3 — PROJECT FACTS

Three finance microservices that you deploy one at a time. They do not call each other at runtime. The top-level repo holds them as embedded git repos (gitlinks, no `.gitmodules`), so commit inside each service first, then record the new gitlink in the top-level repo. Do not convert them to submodules. Each service needs its own `.env` (copy it from `.env.example`). Never commit `.env` files.

| Service | Stack | Port |
|---------|-------|------|
| `risk-management-ms` (FinRisk) | Java 21, Spring Boot 3.3, SQL Server | 8080 when run on the host, 18080 in Docker |
| `hybrid-rag` | Python 3.11, FastAPI, LangChain/LangGraph, FAISS + BM25 | 8000 |
| `sector-valuation-ms` | Node 20 (ESM), Express, Redis, zod | 3000 |

Other top-level folders:
- `landing/`: static marketing site for FinRisk (HTML, CSS and JS, no build step).
- `docs/design-system/`: design tokens and logo.
- `docs/openapi/`: copies of the API specs.
- `README.md`: setup, deploy and usage for all three services.

### Commands

```bash
# risk-management-ms
make dev            # SQL Server container only (then: mvn spring-boot:run)
make up             # SQL Server + API on :18080
make test           # unit tests (mvn test, excludes *IT.java)
make verify         # + integration tests (*IT.java via failsafe, needs SQL Server)
bash db/scripts/apply-migrations.sh FinRiskDB && bash db/scripts/seed.sh FinRiskDB

# hybrid-rag
uvicorn src.api.app:app --reload --port 8000
pytest

# sector-valuation-ms
npm run dev         # node --watch
npm test            # jest with --experimental-vm-modules (ESM)
```

### risk-management-ms
- The package is `com.finrisk`. Code is layered: controller → service → dao (`dao/impl/*Jdbc.java`), plus mapper, dto, model, factory, and `strategy/risk`.
- It uses **plain JDBC, not JPA**. `config/DatabaseConnection` is a HikariCP singleton configured from the env vars `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD`, falling back to `SA_PASSWORD`.
- The schema is in `db/migrations/V1..V5` (schema, indexes, views, procedures, audit triggers). These are applied by script, not Flyway.
- Market data comes from FMP through the `marketdata/MarketDataProvider` interface (`fmp/` holds the implementation). `FMP_API_KEY` is optional.
- Integration tests use the database `FinRiskDB_Test` (`support/IntegrationTestSupport`).
- `target/` is partly tracked in git, so expect diff noise after builds.

### hybrid-rag
- `src/api/app.py` builds the retriever, the LLM and the LangGraph pipeline once at startup and stores them on `app.state`. Routes: `POST /ingest`, `POST /query`, `GET /health`.
- All config is read from env vars in `src/core/config.py`. `LLM_PROVIDER` is `ollama` or `gemini`. `RAG_MODE` is `hybrid`, `semantic` or `lexical`.
- Embeddings and the cross-encoder reranker always run locally (sentence-transformers). The FAISS and BM25 indexes are saved to disk in `CACHE_DIR`.

### sector-valuation-ms
- `src/app.js` exports `createApp({ marketData, cache })`. Tests pass in fakes this way (supertest + `ioredis-mock`). `src/server.js` only starts the server.
- Routes: `POST /api/analyze` (compares one metric to sector peers), `POST /api/dcf`, `POST /api/compare`. Request bodies are validated with zod in `src/validation/schemas.js`.
- Calculations live in pure functions in `src/services/stats.js` and `src/services/dcf.js`.
- The Redis cache fails open: if Redis is down, reads return null and writes do nothing.
- Gotcha: the app reads `REDIS_HOST`/`REDIS_PORT`, but `.env.example` and the README document `REDIS_URL`, which the app ignores.

### Specs & plans
- `docs/superpowers/specs/`: design specs. `2026-07-04-production-readiness-design.md` is approved but not implemented yet. For example, the deposit/withdraw race in `AccountService` is still open.
- `docs/superpowers/plans/`: implementation plans. Only the cross-cutting production-readiness plan exists. The three per-service plans it depends on have not been written.
