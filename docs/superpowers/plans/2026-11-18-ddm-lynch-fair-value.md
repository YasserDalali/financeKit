# DDM and Peter Lynch Fair Value Implementation Plan (sector-valuation-ms)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Every task is TDD (superpowers:test-driven-development): write the failing test, watch it fail, write the minimum code, watch it pass.

**Goal:** Add two valuation endpoints to the DCF service: `POST /api/ddm` (dividend discount model) and `POST /api/lynch` (Peter Lynch fair value).

**Repo / branch:** `sector-valuation-ms/` (its own git repo, currently on `master`), branch `feature/ddm-lynch-fair-value`.

## Global Constraints

- Node 20+, ESM (`import`/`export`), Express 4, zod 3. Run tests with `npm test` from `sector-valuation-ms/` (jest + `--experimental-vm-modules`, supertest). Follow the existing pattern exactly: `src/routes/dcf.js` (router factory taking the injected `marketData`, zod `safeParse` → 400 `{ error: parsed.error.flatten() }`, errors `next(err)`), `src/services/dcf.js` (pure function), `src/validation/schemas.js`, `tests/routes/dcf.test.js` (fake provider), `tests/services/dcf.test.js`.
- Rates are decimals (`0.10` = 10%). Ticker is upper-cased by the schema, like the existing schemas.
- Business-rule failures (no dividend, non-positive EPS or growth) → HTTP `422` with `{ error: "<message>" }`, returned from the route (not thrown). Validation failures stay 400.
- Wire the new routers in `src/app.js` under `/api`, next to the existing ones. Do NOT change `/api/analyze`, `/api/dcf`, `/api/compare` behaviour. Existing tests must keep passing (if extending `getProfile` breaks an exact-shape assertion in `tests/services/marketData.test.js`, update that assertion for the new field).
- Never call the real FMP API in tests (fake provider / mock axios the way existing tests do). Do not commit `coverage/`, `.env`, or anything under `node_modules/`. Commit only the files you create or change, using `git add <paths>`, never `git add -A` or `git commit -a`.
- Commit message style: `feat: add POST /api/<name> ...`.

---

### Task 1: Dividend discount model — `POST /api/ddm`

**Files:** create `src/services/ddm.js`, `src/routes/ddm.js`, `tests/services/ddm.test.js`, `tests/routes/ddm.test.js`; edit `src/validation/schemas.js` (+ `tests/validation/schemas.test.js`), `src/services/marketData/FmpMarketDataProvider.js` (+ `tests/services/marketData.test.js`), `src/services/marketData/index.js`, `src/app.js`.

`computeDDM({ dividendPerShare, discountRate, terminalGrowthRate, highGrowthYears, highGrowthRate, price })` in `src/services/ddm.js` (pure). `dividendPerShare` is the most recent annual dividend `D0`.
- Single stage (when `highGrowthYears` is undefined): `D1 = D0 * (1 + g)`, `intrinsicValue = D1 / (r - g)`, `pvDividends = 0`, `pvTerminal = intrinsicValue`.
- Two stage (when `highGrowthYears` = N and `highGrowthRate` = gh are given): `D_t = D0 * (1 + gh)^t` for t = 1..N, `pvDividends = Σ D_t / (1 + r)^t`; `terminalValue = D_N * (1 + g) / (r - g)`, `pvTerminal = terminalValue / (1 + r)^N`; `intrinsicValue = pvDividends + pvTerminal`.
- `upside = price != null ? (intrinsicValue - price) / price : null`.
- Returns `{ intrinsicValue, pvDividends, pvTerminal, upside }`.

Schema `DdmSchema`: `ticker` (same rule as the others), `dividendPerShare` optional positive number, `discountRate` positive, `terminalGrowthRate` number, `highGrowthYears` optional positive int, `highGrowthRate` optional number. Refinements: `discountRate > terminalGrowthRate` (same message and path as `DcfSchema`), and `highGrowthYears` and `highGrowthRate` must be given together (message `highGrowthYears and highGrowthRate must be provided together`, path `['highGrowthYears']`).

Provider: add `lastDividend` (from FMP profile field `lastDiv`, annual dividend per share; `null` if missing) to the object returned by `getProfile`, and document it on the `MarketDataProvider` base class JSDoc/comment only if the file already documents shapes.

Route `POST /ddm` (factory `createDdmRouter(marketData)`): `profile = await marketData.getProfile(ticker)`; `dividendPerShare = body value ?? profile.lastDividend`; if it is null/undefined or `<= 0` → `422 { error: 'No dividend available for <TICKER>; DDM does not apply' }`. Response: `{ ticker, price: profile.price, dividendPerShare, model: 'gordon' | 'two-stage', ...result }`.

Tests: pure function with hand-computed numbers (Gordon: D0=2, r=0.08, g=0.03 → D1=2.06, value=41.2; and a two-stage case you compute by hand and write the arithmetic in a comment); upside with and without price; schema accepts/rejects (r <= g, half-specified stages); route happy path with body dividend, with dividend from the fake profile, two-stage route, 422 for no dividend (null and 0), 400 for invalid body, error path via `next(err)` like the dcf route test.

### Task 2: Peter Lynch fair value — `POST /api/lynch`

**Files:** create `src/services/lynch.js`, `src/routes/lynch.js`, `tests/services/lynch.test.js`, `tests/routes/lynch.test.js`; edit `src/validation/schemas.js` (+ its test), `src/services/marketData/FmpMarketDataProvider.js` (+ `tests/services/marketData.test.js`), `src/services/marketData/index.js`, `src/app.js`.

`computeLynch({ eps, growthRate, price, dividendYield })` in `src/services/lynch.js` (pure). `growthRate` is a decimal (0.15 = 15%), `dividendYield` a decimal (0.02), may be 0/undefined.
- `growthPct = growthRate * 100`; `fairValue = eps * growthPct` (fair P/E equals growth, i.e. PEG = 1).
- If `price != null`: `pe = price / eps`, `peg = pe / growthPct`, `lynchRatio = (growthPct + (dividendYield ?? 0) * 100) / pe`, `upside = (fairValue - price) / price`; otherwise those four are `null`.
- Returns `{ fairValue, pe, peg, lynchRatio, upside }`. Precondition `eps > 0` and `growthRate > 0` is enforced by the route, not here.

Provider: new method `getEpsGrowth(ticker)` on `FmpMarketDataProvider` (and a throwing stub on the base class like the others) returning `{ eps, epsGrowth }`: `eps` from FMP `GET {base}/v3/income-statement/{ticker}?limit=1` field `eps`; `epsGrowth` from `GET {base}/v3/financial-growth/{ticker}?limit=1` field `epsgrowth` (decimal year-over-year). Throw `Error('EPS data not found for <ticker>')` when the response is empty, like `getFCF`.

Schema `LynchSchema`: `ticker`, `eps` optional number, `growthRate` optional number, `dividendPerShare` optional number `>= 0`.

Route `POST /lynch` (factory `createLynchRouter(marketData)`): `profile = await marketData.getProfile(ticker)`; if `eps` or `growthRate` missing in the body, call `marketData.getEpsGrowth(ticker)` and fill the missing ones (body wins). If `eps <= 0` → `422 { error: 'EPS must be positive for Lynch fair value' }`; if `growthRate <= 0` → `422 { error: 'Growth rate must be positive for Lynch fair value' }`. `dividendYield = (body dividendPerShare ?? profile.lastDividend ?? 0) / profile.price`. Response: `{ ticker, price: profile.price, eps, growthRate, ...result }`.
Depends on Task 1 only for `lastDividend` on `getProfile` (already added there) and the `app.js` wiring pattern.

Tests: pure function with hand-computed numbers (eps=5, growth 0.20 → fairValue 100; price 80 → pe 16, peg 0.8, upside 0.25; lynchRatio with dividendYield 0.02 → (20+2)/16 = 1.375); no price → nulls; route with eps and growth in body (provider's `getEpsGrowth` must not be called), with both fetched, with one fetched; 422 for negative EPS and for zero/negative growth; 400 for invalid body; provider error → `next(err)`; provider test for `getEpsGrowth` parsing and empty-response error (mock axios the way the existing provider tests do).
