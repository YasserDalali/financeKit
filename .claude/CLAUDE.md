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

### Commands

```bash
# Run all tests (from repo root)
npm test

# Run all tests (from api/)
cd api && npx vitest run

# Run a single test file
cd api && npx vitest run test/loans.spec.ts

# Run a single test by name
cd api && npx vitest run -t "test name substring"

# Local dev server
npm run dev          # wrangler dev

# Deploy
npm run deploy       # builds frontend then wrangler deploy

# Apply DB migrations (remote)
wrangler d1 migrations apply microloans_db
```

### Architecture

**Single Cloudflare Worker** (`api/src/index.ts`) serving a Hono router. No separate services. Frontend is a static SPA built separately (lives in `frontend/`; served via Cloudflare Pages or Workers Assets).

**Bindings** (declared in `wrangler.toml`, typed in `api/src/types.ts`):
- `DB` — D1 (SQLite). Schema in `api/migrations/0001_initial_schema.sql`. Six tables: `users`, `profiles`, `loans`, `installments`, `transactions`, `audit_logs`.
- `LOAN_CACHE` — KV. Used for JWT drafts, KYC upload drafts (1h TTL), and rate limiting.
- `KYC_BUCKET` — R2. Stores raw KYC document images at `kyc/{userId}/{uuid}`.
- `JWT_SECRET`, `TURNSTILE_SECRET`, `PII_ENCRYPTION_KEY`, `GEMINI_API_KEY` — secrets via `.dev.vars` locally.

**Route layout** (`api/src/routes/`):
- `POST /api/auth/register` — Turnstile-gated, hashes password (scrypt via `auth/password.ts`), inserts user as `borrower`.
- `POST /api/auth/login` — Turnstile-gated, returns HS256 JWT (1h expiry).
- `POST /api/kyc/upload` — Auth-gated. Accepts JPEG/PNG ≤5 MB, writes to R2, calls Gemini OCR, caches draft in KV.
- `POST /api/kyc/confirm` — Consumes KV draft, encrypts PII fields with AES-GCM, writes to `profiles`.
- `POST /api/loans/` — Creates a `pending` loan (hardcoded 5% flat rate).
- `GET /api/loans/:id` — Returns loan + installment schedule.
- `POST /api/loans/:id/approve` — `officer`/`admin` only. Sets loan `active`, inserts installments + disbursement transaction in a D1 batch.
- `POST /api/loans/:id/installments/:installmentId/pay` — Records repayment, transitions loan to `fully_paid` when all installments are settled.

**PII encryption** (`api/src/crypto.ts`): AES-GCM with a random 12-byte IV. Stored as `base64(iv):base64(ciphertext)`. All `profiles` columns except `user_id`, `kyc_status`, `kyc_document_r2_key` are encrypted.

**KYC OCR** (`api/src/kyc/ocr.ts`): Calls Gemini `gemini-2.5-flash` (not 2.0-flash — it has quota=0 on this key). Extracts `firstName`, `lastName`, `nationalIdNumber`, `dob` as JSON. Falls back to all-null on parse failure.

**Auth middleware** (`api/src/middleware/`):
- `requireAuth` — verifies HS256 JWT, sets `c.var.userId/role/jti/exp`.
- `requireRole(...roles)` — checks `c.var.role` against allowed list.
- `turnstile.ts` — standalone `verifyTurnstile()` helper, fail-closed on transport error.

**JWT** (`api/src/auth/jwt.ts`): Hand-rolled HS256 using `crypto.subtle`. Constant-time compare on signature to prevent timing attacks.

### Testing

Tests run inside `@cloudflare/vitest-pool-workers` (real miniflare runtime, not mocks). Key seams:

- `fetchMock` from `cloudflare:test` (not `jest.spyOn(globalThis, 'fetch')`) — required for intercepting outbound fetch in the Workers runtime.
- R2 assertions use `.head(key)` not `.get(key)` — `.get()` returns `null` for empty bodies in some miniflare versions.
- `TURNSTILE_SECRET` is pinned to `1x0000000000000000000000000000000AA` (Cloudflare always-pass test secret) via `vitest.config.ts` miniflare bindings — tests don't need a real token.
- `TEST_MIGRATIONS` binding is injected by `vitest.config.ts`; `test/apply-migrations.ts` applies them once as a global setup file.

### Specs & plans

- `docs/superpowers/specs/` — design specs (e.g. KYC/OCR pipeline).
- `docs/superpowers/plans/` — implementation plans.
- `CLOUDFLARE_MICROLOAN_PLAN.md` — original architectural blueprint.
