# Plan: portfolio analytics + DCF extras

Two independent branches in two separate git repos, so they can run side by side. Inside each repo, tasks run one at a time. Each task is done with TDD (failing test, then code, then green) and gets a review.

## Facts I found (so the plan isn't guessing)

- `risk-management-ms` is on `main`. It has a pre-existing uncommitted change to `openapi.yaml` and tracked `target/` output. Implementers commit only the paths they create.
- `BetaService` is the pattern to copy. It lines up asset history (`AssetPriceHistoryDao.latestPrices`) against SPY (`MarketDataProvider.fetchDailyPrices`) by position, over 90 days, using log returns. The new endpoints use the same approach, so they inherit its simplifications: no date alignment, and the portfolio is built from today's holdings and weights applied to past prices.
- Tests there are Mockito unit tests (`*ServiceTest`, no database needed). `*IT.java` needs SQL Server and is out of scope.
- `sector-valuation-ms` is on `master`. `src/services/dcf.js` and `stats.js` are pure functions. Routes get the market-data provider injected, and tests fake it (`tests/routes/dcf.test.js`).
- Neither the `MarketDataProvider` interface in risk-management-ms nor the one in sector-valuation-ms has ETF holdings or dividend or EPS data yet.

## Branch A: `risk-management-ms`, branch `feature/portfolio-analytics-extras`

All routes are `GET /api/v1/accounts/{accountId}/...` and live in `PortfolioController`. Each has its own service, response record and unit test. A shared small `ReturnsMath` helper (log returns, mean, stdev, covariance) is added so the new services don't each copy it. `BetaService` is left alone.

| # | Endpoint | What it returns |
|---|----------|-----------------|
| A1 | `/correlation` | Pairwise Pearson correlation matrix of holdings (log returns), plus average pairwise correlation. Needs at least 2 holdings. |
| A2 | `/drawdown` | Max drawdown and current drawdown for the portfolio (today's weights applied to past prices), and max drawdown per holding. |
| A3 | `/alpha` | Jensen's alpha vs SPY, annualised: `Rp - (rf + beta * (Rm - rf))`. Uses the portfolio beta from `BetaService`. Optional `?riskFree=` query parameter, default 0. |
| A4 | `/downside` | See open question 1. Default: downside deviation (target return 0), Sortino ratio, downside beta vs SPY, worst single-day return. |
| A5 | `/etf-look-through` and `/etf-overlap` | Look-through expands each ETF holding into its underlying stocks (via a new `MarketDataProvider.fetchEtfHoldings`) and returns the portfolio's effective weight per underlying stock, direct plus via ETFs. Overlap returns, for each pair of ETFs, the overlap percentage (sum of the smaller weight of each shared stock) and the shared stocks. |

Edge cases each endpoint handles (and has a test for): unknown account returns 404 (`AccountNotFoundException`), empty portfolio returns an empty, well-formed response, and too few price samples returns a safe default as `BetaService` does.

## Branch B: `sector-valuation-ms`, branch `feature/ddm-lynch-fair-value`

| # | Endpoint | What it does |
|---|----------|--------------|
| B1 | `POST /api/ddm` | Dividend discount model. Gordon growth when only a terminal rate is given: `D1 / (r - g)`. Two-stage when `highGrowthYears` and `highGrowthRate` are given. Dividend per share comes from the request or, if omitted, from FMP (new `getDividend` provider method). Rejects `r <= g`. Returns `intrinsicValue`, `upside`, and the inputs used. A stock that pays no dividend returns a clear 422 instead of 0. |
| B2 | `POST /api/lynch` | Peter Lynch fair value: `EPS * (earnings growth in % )` (a PEG of 1), plus `peg` and the dividend-adjusted Lynch ratio `(growth% + dividend yield%) / PE`. EPS and growth come from the request or from FMP (new `getEps` provider method). Non-positive EPS or growth returns 422. |

Both follow the pattern of `src/routes/dcf.js`: a zod schema in `src/validation/schemas.js`, a pure function in `src/services/`, a router factory wired in `src/app.js`, and tests with a fake provider.

## Process

1. Create the branches (see open question 2 for how).
2. Per repo, in task order: record the base commit, dispatch one implementer (TDD, commits only its own files), generate the review package, dispatch a reviewer (spec and quality), fix anything Critical or Important, then record the task in `.superpowers/sdd/progress.md`.
3. Per repo, one final whole-branch review at the end.
4. Verify: `mvn -B test` in risk-management-ms, `npm test` in sector-valuation-ms.

## Not doing (unless you say so)

- No changes to `openapi.yaml`, `openapi.json` or `docs/openapi/`. `openapi.yaml` already has uncommitted edits, so I'd be mixing my work into yours.
- No refactor of `BetaService`, and no fix for the position-based price alignment.
- No `/api/compare` changes to include DDM or Lynch.
- No integration tests (they need SQL Server).
- No push, no PR.

## Open questions

1. "Downside exposure": which of these do you mean? The default in A4 is downside deviation plus Sortino plus downside beta plus worst day.
2. Branching in `risk-management-ms`: switch branches in place (the dirty `openapi.yaml` rides along but isn't committed), or use a separate worktree (clean checkout, needs its own Maven build)?

---

# Plan: `data-ms` — free data sources behind interfaces

Status: **proposed, waiting for go-ahead.** Nothing built yet.

## Goal

A new service, `data-ms`, whose only job is to fetch and normalise free third-party data. Everything else in FinanceKit depends on **interfaces** (ports), never on a source. Swapping or adding a source is a config change plus one adapter file. Quality refactor comes later; for now we keep sources and code decoupled and nothing more.

## Source decisions (free only, usable in a public app)

| Keep | Used for | Needs |
|------|----------|-------|
| SEC EDGAR | statements (XBRL `companyfacts`), filings text, insider trades (Form 4), institutional holders (13F) | `User-Agent` with a contact (`SEC_USER_AGENT`), max 10 req/s |
| FRED | rates, inflation, GDP, unemployment, recession flags | free key (`FRED_API_KEY`) |
| World Bank | country macro series | none; CC BY 4.0, so attribution is returned with every result |
| GDELT (open DOC 2.0 API) | geopolitical event volume and tone | none |
| UN Comtrade | trade flows for supply-chain scenarios | free key (`COMTRADE_API_KEY`), capped, so always cached |

| Drop | Why |
|------|-----|
| yfinance, Alpha Vantage | data rights not cleared for a public app |
| Tiingo, SimFin | internal or non-commercial use only |
| GDELT Cloud | free tier excludes production |
| Open Supply Hub | API is paid |

Out of scope: **analyst consensus** has no free source on the list. Cut it from the product promises (landing carousel card 05 and the brief). The existing FMP calls in `risk-management-ms` and `sector-valuation-ms` are untouched.

## The interfaces (the contract)

Plain Node ESM, same style as `sector-valuation-ms`: a base class per port whose methods throw `not implemented`, JSDoc types, adapters `extends` it. Every method returns a `DataResult<T>`: `{ data, source, asOf, attribution }`, so licence attribution travels with the data. Failures throw `DataSourceError` with `code` in `NOT_FOUND | RATE_LIMITED | UNAVAILABLE | INVALID_INPUT`.

| Port | Methods | Implemented by |
|------|---------|----------------|
| `FundamentalsSource` | `getStatements(ticker, { period, limit })` → normalised income, balance sheet, cash flow | EDGAR |
| `FilingsSource` | `listFilings(ticker, { forms, limit })`, `getFilingText(accession)` | EDGAR |
| `InsiderSource` | `getInsiderTransactions(ticker, { since })` | EDGAR (Form 4) |
| `InstitutionalSource` | `getInstitutionalHolders(ticker, { quarter })` | EDGAR (13F) |
| `MacroSeriesSource` | `getSeries({ seriesId, country?, from?, to? })` → `{ id, title, unit, frequency, points: [{ date, value }] }` | FRED, World Bank |
| `EventSource` | `getEventSignals({ theme, country?, from, to })` → `[{ date, volume, avgTone }]` | GDELT |
| `TradeFlowSource` | `getTradeFlows({ reporter, partner?, commodity, year })` → `[{ reporter, partner, commodity, flow, valueUsd, year }]` | Comtrade |

A **registry** (`src/registry.js`) is the only file that imports adapters. It builds each port from env config (`MACRO_SOURCE=fred|worldbank`, etc.). Routes and anything above them receive ports through injection. An optional Redis cache wraps any port with per-method TTLs (same degrade-gracefully behaviour as `sector-valuation-ms`).

## Known risk to flag before building

13F is filed **by the investor, not by the company**, so "who holds AAPL" means aggregating a whole quarter's filings. EDGAR has no direct lookup. MVP option: top N holders from one quarter's bulk filings, cached. If that's too heavy, `InstitutionalSource` ships as interface-only and we decide later.

## Tasks (TDD, one at a time, commit per task)

1. Scaffold `data-ms` (Node ESM, express, jest, `/health`), shared `DataResult` and `DataSourceError`, port base classes with a contract test helper that every adapter and fake must pass.
2. Registry, config and the optional cache wrapper, with fake in-memory adapters for all ports.
3. `FredMacroSource` and `WorldBankMacroSource` (both `MacroSeriesSource`).
4. `EdgarFundamentalsSource` and `EdgarFilingsSource` (ticker → CIK lookup, XBRL normalisation, rate limiting).
5. `EdgarInsiderSource` (Form 4).
6. `GdeltEventSource`.
7. `ComtradeTradeFlowSource`.
8. `EdgarInstitutionalSource` (see risk above; may stop at interface).
9. Thin `GET` routes, one per port, plus README with env vars. This is what the other services call.

Adapter tests use recorded fixtures through an injected HTTP client; no test hits the network.

## Not doing

- No changes to the three existing services, the landing page or `openapi` files.
- No wiring of `risk-management-ms` or `sector-valuation-ms` to `data-ms` yet.
- No push, no PR.

---

# Plan: Java modular monolith (proposed, waiting for go-ahead)

Full plan with code and commands: `docs/superpowers/plans/2026-11-19-java-modular-monolith.md` (14 tasks).

One Java 21 / Spring Boot app in `backend/` replaces `risk-management-ms`, `sector-valuation-ms` and the planned `data-ms`. Contexts: Data (`MarketData` interface, FMP then Yahoo adapters, failover, cache), Valuation (ported from Node), Portfolio + Risk (moved and moved to PostgreSQL). `hybrid-rag` stays the one extra service. Deploy: `render.yaml` Blueprint (Render cannot run docker-compose) plus a local `docker-compose.yml`.

Decisions to confirm before executing (details in the plan header):
1. Render cannot run compose files, so there are two artifacts built from the same Dockerfiles.
2. PostgreSQL replaces SQL Server (confirmed earlier).
3. In-memory Caffeine cache replaces Redis.
4. Yahoo is an unofficial fallback, on by default, with a kill switch (`YAHOO_ENABLED=false`).
5. Shares-outstanding source fixed to the income statement; DCF rejects non-positive free cash flow.
6. Old service repos move to `~/finrisk-archive/`; `hybrid-rag` is vendored into the main repo so Render can build it.
