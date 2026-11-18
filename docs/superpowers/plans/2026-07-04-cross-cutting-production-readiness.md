# Cross-Cutting Production Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a root docker-compose that runs the whole financeKit stack, fix the stale/incomplete repo docs, and bring all four git repos (parent + three services) to a clean committed state.

**Architecture:** The three services stay independently deployable; a root `docker-compose.yml` composes their hardened images plus SQL Server and Redis with healthcheck-ordered startup. Docs work is textual only. Commit hygiene touches each embedded repo, then records the new gitlinks in the parent.

**Tech Stack:** Docker Compose v2, Markdown, git.

## Global Constraints

- **Prerequisite:** the three service plans (`2026-07-04-risk-management-ms-production-readiness.md`, `2026-07-04-sector-valuation-ms-production-readiness.md`, `2026-07-04-hybrid-rag-production-readiness.md`) are complete — this plan consumes the sector-valuation Dockerfile and the HEALTHCHECKs those plans add.
- Host ports stay as today: FinRisk **18080**, sector-valuation **3000**, hybrid-rag **8000**, SQL Server **1433**, Redis **6379**.
- The parent repo tracks the services as gitlinks (embedded repos, no `.gitmodules`) — do not convert to submodules.
- Never commit secrets; `.env` files stay untracked everywhere.
- No pushes to any remote — commits only.
- Working directory for parent-repo commands: `/home/yasser/Desktop/Big-5/financeKit`.

---

### Task 1: Root docker-compose.yml + root .env.example

**Files:**
- Create: `docker-compose.yml` (repo root)
- Create: `.env.example` (repo root)
- Create: `.gitignore` (repo root — parent repo has none; ignore `.env`)

**Interfaces:**
- Consumes: `risk-management-ms/Dockerfile`, `sector-valuation-ms/Dockerfile`, `hybrid-rag/Dockerfile` (hardened by the service plans), `risk-management-ms/docker-compose.yml` (sqlserver definition copied verbatim minus sonarqube).
- Produces: `docker compose up` at repo root runs 5 containers: `finrisk-sqlserver`, `risk-management-api`, `sector-valuation`, `financekit-redis`, `hybrid-rag`.

- [ ] **Step 1: Write root `.gitignore`**

```gitignore
.env
```

- [ ] **Step 2: Write root `.env.example`**

```bash
# FinanceKit root compose environment. Copy to `.env` (never commit `.env`).

# --- FinRisk (SQL Server) ---
# Password policy: >=8 chars, three of: upper, lower, digit, symbol.
# Single-quote passwords containing $ or ! .
SA_PASSWORD='FinRisk_Dev_8x!'
DB_NAME=FinRiskDB

# --- Shared: FinancialModelingPrep (FinRisk price sync + sector-valuation) ---
FMP_API_KEY=

# --- hybrid-rag LLM provider: "ollama" or "gemini" ---
LLM_PROVIDER=ollama
# Ollama runs on the host; host-gateway mapping makes this resolvable from the container.
OLLAMA_BASE_URL=http://host.docker.internal:11434
GEMINI_API_KEY=
```

- [ ] **Step 3: Write root `docker-compose.yml`**

```yaml
services:
  sqlserver:
    image: mcr.microsoft.com/mssql/server:2022-latest
    container_name: finrisk-sqlserver
    environment:
      ACCEPT_EULA: "Y"
      MSSQL_SA_PASSWORD: ${SA_PASSWORD:?set SA_PASSWORD}
      MSSQL_PID: Developer
    ports:
      - "1433:1433"
    volumes:
      - sqlserver_data:/var/opt/mssql
    healthcheck:
      test:
        [
          "CMD-SHELL",
          "/opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P \"$$MSSQL_SA_PASSWORD\" -Q \"SELECT 1\" -b -o /dev/null",
        ]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 40s

  risk-management-api:
    build:
      context: ./risk-management-ms
      dockerfile: Dockerfile
    container_name: risk-management-api
    depends_on:
      sqlserver:
        condition: service_healthy
    environment:
      SPRING_PROFILES_ACTIVE: docker
      DB_HOST: sqlserver
      DB_PORT: "1433"
      DB_NAME: ${DB_NAME:-FinRiskDB}
      DB_USER: sa
      DB_PASSWORD: ${SA_PASSWORD:?set SA_PASSWORD}
      SA_PASSWORD: ${SA_PASSWORD:?set SA_PASSWORD}
      FMP_API_KEY: ${FMP_API_KEY:-}
    ports:
      - "18080:8080"

  redis:
    image: redis:7-alpine
    container_name: financekit-redis
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  sector-valuation:
    build:
      context: ./sector-valuation-ms
      dockerfile: Dockerfile
    container_name: sector-valuation
    depends_on:
      redis:
        condition: service_healthy
    environment:
      REDIS_URL: redis://redis:6379
      FMP_API_KEY: ${FMP_API_KEY:-}
      PORT: "3000"
    ports:
      - "3000:3000"

  hybrid-rag:
    build:
      context: ./hybrid-rag
      dockerfile: Dockerfile
    container_name: hybrid-rag
    environment:
      LLM_PROVIDER: ${LLM_PROVIDER:-ollama}
      OLLAMA_BASE_URL: ${OLLAMA_BASE_URL:-http://host.docker.internal:11434}
      GEMINI_API_KEY: ${GEMINI_API_KEY:-}
      CACHE_DIR: /app/cache
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - hybrid_rag_cache:/app/cache
    ports:
      - "8000:8000"

volumes:
  sqlserver_data:
  hybrid_rag_cache:
```

- [ ] **Step 4: Validate compose syntax**

Run: `cd /home/yasser/Desktop/Big-5/financeKit && cp -n .env.example .env; docker compose config --quiet && echo OK`
Expected: `OK` (no warnings about missing env vars)

- [ ] **Step 5: Build and start the stack**

Run: `docker compose up -d --build && docker compose ps`
Expected: 5 containers; `finrisk-sqlserver` and `financekit-redis` become `healthy`; the three APIs `running`.

- [ ] **Step 6: Apply FinRisk migrations (first boot only) and smoke-test all services**

```bash
cd risk-management-ms && set -a && source .env 2>/dev/null; set +a; bash db/scripts/apply-migrations.sh FinRiskDB; cd ..
curl -sf http://localhost:18080/actuator/health
curl -sf http://localhost:3000/health
curl -sf http://localhost:8000/health
```

Expected: three JSON bodies, each reporting healthy/ok status. (FinRisk migration step uses the service-level `.env`; if absent, export `SA_PASSWORD` from the root `.env` first.)

- [ ] **Step 7: Commit (parent repo)**

```bash
git add docker-compose.yml .env.example .gitignore
git commit -m "feat: add root docker-compose running the full financeKit stack

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: README updates

**Files:**
- Modify: `README.md` (repo root)

**Interfaces:**
- Consumes: root `docker-compose.yml` from Task 1; the sector-valuation Dockerfile from the service plan.
- Produces: docs consistent with the fixed code.

- [ ] **Step 1: Add a "Run the whole kit" section**

Insert after the intro table (after the line `Central copies of the API specs live in [\`docs/openapi/\`](./docs/openapi/).`):

```markdown
## Run the whole kit (Docker Compose)

```bash
cp .env.example .env   # set SA_PASSWORD; optionally FMP_API_KEY, LLM provider vars
docker compose up -d --build

# First boot: apply FinRisk migrations
bash risk-management-ms/db/scripts/apply-migrations.sh FinRiskDB

curl -sf http://localhost:18080/actuator/health   # FinRisk
curl -sf http://localhost:3000/health             # sector-valuation
curl -sf http://localhost:8000/health             # hybrid-rag
```

All three APIs plus SQL Server and Redis start with healthcheck-ordered dependencies. Services remain independently deployable; see each service section below.
```

- [ ] **Step 2: Fix the sector-valuation Redis + Docker documentation**

In the sector-valuation sections: document `REDIS_URL` as the primary variable with `REDIS_HOST`/`REDIS_PORT` fallback. Replace the "No Dockerfile is included." paragraph under "Production build and deploy → Sector Valuation" with:

```markdown
**Build and run**

```bash
cd sector-valuation-ms
docker build -t financekit-sector-valuation .
docker run -d \
  --name sector-valuation \
  -p 3000:3000 \
  -e FMP_API_KEY=... \
  -e REDIS_URL=redis://your-redis-host:6379 \
  financekit-sector-valuation
```

Run behind a reverse proxy and use a managed Redis instance for the peer cache.
```

- [ ] **Step 3: Document the hybrid-rag cache-volume trust assumption**

In the hybrid-rag production section, after the volume-mount paragraph, add:

```markdown
The FAISS index is loaded with pickle deserialization (`allow_dangerous_deserialization=True` — required by LangChain for local indexes). Treat the cache volume as trusted: never mount cache data from untrusted sources.
```

- [ ] **Step 4: Verify and commit**

Run: `grep -n "Run the whole kit" README.md && grep -n "REDIS_URL" README.md && ! grep -n "No Dockerfile is included" README.md && echo DOCS-OK`
Expected: matches for the first two, no match for the removed line, `DOCS-OK`.

```bash
git add README.md
git commit -m "docs: whole-kit compose instructions, Redis/Docker doc fixes

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Rewrite .claude/CLAUDE.md Tier 3 for financeKit

**Files:**
- Modify: `.claude/CLAUDE.md`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: accurate project instructions for future Claude sessions.

- [ ] **Step 1: Replace the stale TIER 3 section**

Keep TIER 1 (hard rules) and TIER 2 (workflow) exactly as they are — they are the user's workflow preferences. Replace everything from `## TIER 3 — PROJECT FACTS` to the end of the file with:

```markdown
## TIER 3 — PROJECT FACTS

financeKit is a monorepo of three independent financial microservices. Each service directory is its own git repo (tracked as gitlinks in the parent — commit inside the service first, then update the parent).

| Service | Stack | Port | Tests |
|---------|-------|------|-------|
| `risk-management-ms` | Spring Boot 3.3.6, Java 21, raw JDBC, SQL Server | 8080 (host 18080 via compose) | `cd risk-management-ms && mvn test` |
| `hybrid-rag` | FastAPI, LangChain/LangGraph, FAISS + BM25 | 8000 | `cd hybrid-rag && ./venv/bin/python -m pytest -q` |
| `sector-valuation-ms` | Node 20, Express, Zod, Redis, FMP API | 3000 | `cd sector-valuation-ms && npm test` |

### Commands

```bash
# Whole kit (from repo root)
cp .env.example .env && docker compose up -d --build

# FinRisk dev loop
cd risk-management-ms && make dev && mvn spring-boot:run   # SQL Server in Docker, API on host :8080
bash db/scripts/apply-migrations.sh FinRiskDB              # migrations (first boot / after wiping volume)

# hybrid-rag dev loop
cd hybrid-rag && uvicorn src.api.app:app --reload --port 8000

# sector-valuation dev loop
cd sector-valuation-ms && npm run dev
```

### Architecture notes

- Services do not call each other at runtime; FinRisk and sector-valuation share only the FMP API key pattern.
- FinRisk: raw-JDBC DAOs (`dao/impl`), services in `service/`, money-path writes use atomic conditional SQL — keep it that way.
- hybrid-rag: retrieval state (`HybridRetriever`) is guarded by an internal lock; blocking pipeline work runs via `asyncio.to_thread` — never call it directly in async routes.
- sector-valuation: Redis config comes from `REDIS_URL` (host/port fallback); FMP nulls must be rejected before DCF math.
- No authentication by design — services deploy behind a trusted gateway/VPN (documented in README).
- Specs: `docs/superpowers/specs/`. Plans: `docs/superpowers/plans/`. Central OpenAPI copies: `docs/openapi/`.
```

- [ ] **Step 2: Verify and commit**

Run: `grep -c "microloans\|Cloudflare\|wrangler\|Turnstile" .claude/CLAUDE.md || echo CLEAN`
Expected: `0` or `CLEAN` (no stale content remains).

```bash
git add .claude/CLAUDE.md
git commit -m "docs: rewrite CLAUDE.md project facts for financeKit

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Commit hygiene across all four repos

**Files:**
- Modify: `risk-management-ms/.gitignore` (ensure `target/` ignored)
- Commit in: `risk-management-ms`, `hybrid-rag` (service repos), then the parent repo.

**Interfaces:**
- Consumes: all previous work (service plans' commits already exist inside each service repo).
- Produces: `git status` clean in all four repos (except intentionally untracked `.env` files and venv).

- [ ] **Step 1: risk-management-ms — ignore build artifacts, commit spec files**

```bash
cd /home/yasser/Desktop/Big-5/financeKit/risk-management-ms
grep -qx 'target/' .gitignore || echo 'target/' >> .gitignore
git add .gitignore openapi.yaml openapi.json
git commit -m "docs: commit OpenAPI spec updates; ignore build artifacts

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
git status --short
```

Expected: status shows nothing except possibly untracked local-only files; `target/` no longer listed.

- [ ] **Step 2: hybrid-rag — commit the OpenAPI export**

```bash
cd /home/yasser/Desktop/Big-5/financeKit/hybrid-rag
git add openapi.json
git commit -m "docs: commit OpenAPI export

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
git status --short
```

Expected: clean status (venv/, cache/, .env are gitignored).

- [ ] **Step 3: Parent repo — commit docs and updated gitlinks**

```bash
cd /home/yasser/Desktop/Big-5/financeKit
git add README.md docs/openapi/ docs/superpowers/plans/ risk-management-ms hybrid-rag sector-valuation-ms
git commit -m "chore: commit repo docs and record hardened service states

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
git status --short
```

Expected: clean (only `.env` untracked, which `.gitignore` from Task 1 hides).

- [ ] **Step 4: Final verification — whole-kit smoke**

```bash
cd /home/yasser/Desktop/Big-5/financeKit
docker compose up -d --build
sleep 5
curl -sf http://localhost:18080/actuator/health && \
curl -sf http://localhost:3000/health && \
curl -sf http://localhost:8000/health && echo SMOKE-OK
```

Expected: `SMOKE-OK`.
