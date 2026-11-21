# What we store, how long it stays valid, and what we may keep

Status: design, 2026-11-21. Companion to `contracts.md` and `waterfall.md`. Terms of use are summarised from `inventory.md` research **[V]** or prior knowledge **[K]**; this is not legal advice, so re-read a provider's terms before relying on a row.

## 1. Most financial data does not expire, it grows

Market and filing history is a fact about the past. A closing price for 2019-03-04 or a 10-K filed in 2021 does not change, so we keep it and fetch only what is new (a **delta fetch**, "everything after the last date I hold"). We never invalidate history.

Four storage classes cover every resource:

| Class | What it means | Read path | Examples |
|---|---|---|---|
| **Immutable history** | Rows never change once written | delta fetch after the last stored key | raw daily close, dividends, splits, Form 4 trades, filings, 13F quarters, N-PORT quarters |
| **Revisable history** | New rows arrive, and a known trailing window gets revised | delta fetch + refetch the revision window | GDP, payrolls, seasonally adjusted CPI, trade flows, French factors |
| **Snapshot** | One current value that can change | refetch after its TTL, keep dated versions | profile and sector, peers, issuer ETF holdings, next earnings date, current-month ratings |
| **Live only** | The terms forbid storing it | fetch per request, never persist | anything served by FRED |

### The one trick that makes prices immutable

An *adjusted* close for a past date changes every time a later dividend or split happens. A *raw* close never does. So we store the **raw close plus the corporate actions** (dividends, splits) and compute `adjClose` when we read. Past price rows then never need rewriting. This changes the stored shape from `contracts.md` (`PricePoint(date, adjClose)`) into `PriceBar(date, close)` + `Dividend` + `Split`; the domain-facing `PricePoint(date, adjClose)` stays as it is.

When a delta fetch comes from a different layer than the rows already stored, the adapter refetches the last stored day and compares it. If the two closes differ by more than 0.5 %, it reloads the full window from the new layer instead of mixing them. This matters because Alpaca's free feed is IEX-only and its close can differ from the consolidated close that Tiingo and Yahoo report.

## 2. Freshness per resource

- **Fresh TTL**: inside this window the stored value is served without any call.
- **Revision window**: on each refresh, this trailing slice is refetched because the source revises it.
- **Max stale**: when every live layer fails, the stored value is still served with a warning up to this age. Past it, the response says the data is unavailable.

| Resource | Class | New data | Fresh TTL | Revision window | Max stale (with warning) |
|---|---|---|---|---|---|
| prices (raw close) | immutable | each trading day | until next close | none | 10 trading days |
| dividends, splits | immutable | on event | 1 day | none | 30 days |
| risk_free | immutable | each business day | 1 day | none | 10 business days |
| sector / profile | snapshot | rare | 90 days | — | 1 year |
| etf_holdings (N-PORT) | immutable per quarter | quarterly, about 60-day lag | until the next quarterly file | — | 6 months |
| etf_holdings (issuer, Yahoo) | snapshot | daily | 1 day / 7 days | — | 30 days |
| statements | immutable facts | each 10-Q / 10-K | 1 day near a filing due date, else 7 days | none: a restatement arrives as a new fact with a later `filed` date, and we keep both | 1 year |
| ratios | derived, not stored | — | recomputed on read | — | follows its inputs |
| peers | snapshot | rare | 30 days | — | 1 year |
| us_macro | revisable | monthly / quarterly release | until the next release date | GDP 3 yrs, payrolls 2 months (plus the annual benchmark), seasonally adjusted CPI 5 yrs each February | 3 months |
| global_macro | revisable | annual | 30 days | 2 years | 2 years |
| factor_history | revisable | monthly | 30 days | full refresh once a year (French restates history) | 1 year |
| recession | snapshot | NBER announcements (rare) | 180 days | — | no limit |
| commodities | immutable | daily (EIA updates weekly) | 1 day | none | 30 days |
| trade_flows | revisable | annual | 30 days | last 2 years | no limit (annual data) |
| institutional (13F) | immutable per quarter | quarterly, 45-day lag | until the next filing window | amendments (13F-A) within the quarter | 1 quarter past the window |
| insiders (Form 4) | immutable | on event (2 business days) | 1 day | none | 30 days |
| filings | immutable | on event | 1 day | none | 30 days |
| ratings | immutable per month + current-month snapshot | monthly | 7 days | current month only | 3 months |
| earnings_calendar | snapshot | dates can move | 1 day, 6 hours in the last week before the date | — | until the date passes |
| identifier maps (CUSIP, CIK ↔ ticker) | snapshot | ticker changes | 90 days | — | 1 year |

### Read order with a stale fallback

```text
1. stored value inside its fresh TTL  → serve it (no call)
2. live layers 1..N in waterfall order → first complete answer wins, stored, served
3. all layers failed or out of quota  → stored value up to max stale, served with a warning
4. nothing usable                     → empty, the domain skips the metric
```

Every response carries `Freshness(asOf, source, stale)`. The UI shows a small notice when `stale` is true, for example: "Prices as of 14 Nov from Tiingo. Live sources unavailable." A stale value from layer N is in canonical form, so it does not matter which layer produced it.

## 3. What we may store (compliance constraints)

The app runs on a public Render URL. Even without income, showing vendor data to anyone who opens the URL can count as redistribution. That is the binding constraint, more than storage itself.

| Rights | Sources | Constraint |
|---|---|---|
| **Store and show freely** | SEC EDGAR (all sets), US Treasury, BLS, BEA, EIA, NY Fed, NBER dates, OpenFIGI mappings | public domain or free without restriction; SEC needs a declared User-Agent and at most 10 req/s **[V]** |
| **Store and show, with attribution** | World Bank (CC BY 4.0), OECD, IMF, Kenneth French, Shiller | cite the source wherever the data is shown **[K]** |
| **Store for personal use, do not redistribute** | Alpaca, Tiingo, Finnhub, Yahoo, Alpha Vantage, UN Comtrade (non-commercial) | fine for you; risky if strangers can see the data on a public page **[V/K]** |
| **Terms unknown** | issuer holdings CSVs (iShares, SPDR, Vanguard) | do not scrape until the terms are read **[?]** |
| **Do not store** | FRED | API terms forbid storing, caching or archiving **[V]**: live only, never persisted, no stale fallback |

What follows from this:
1. **Put the app behind a login** (you plus invited users). That keeps vendor-sourced data in personal use. A public demo page can still show anything sourced from the first two rows.
2. **Record the source on every stored row** (`source` column). We can then purge one vendor's rows if its terms change, and show attribution.
3. **FRED stays a live-only last resort.** It is never written to the store, so it never appears as stale data. That is one more reason its score ranks it last.

## 4. A database, with a small cache in front

Recommendation: **PostgreSQL as the store of record, Caffeine in memory for hot reads. No Redis.**

- History is the asset. Twenty years of prices and filings are expensive to re-pull (quotas) and slow (bulk files), so they must survive restarts and redeploys. Render's instance disk is wiped on each deploy, so an in-process cache alone would refetch everything after every deploy.
- Delta fetch needs "what is the last date I hold for X?", which is a single indexed query in a database.
- Peers, look-through and multiples join several datasets. That is a query, not a key lookup.
- Postgres is already in the plan (portfolio context). The market-data tables live in their own schema, `marketdata`, so the bounded contexts stay separate.
- Caffeine (already used by `CachingMarketData`) keeps the hot answers in memory for minutes, so most reads never reach the database.

Tables (one row = one fact, plus `source` and `fetched_at` on each):

| Table | Key | Class |
|---|---|---|
| `price_bar` | symbol, date | immutable |
| `corporate_action` | symbol, ex_date, kind | immutable |
| `statement_fact` | cik, line_item, period_end, period_type, filed | immutable (restatements append) |
| `macro_point` | series_id, date | revisable (upsert inside the window) |
| `fund_holding` | etf, as_of, holding_symbol | immutable per as_of |
| `institutional_position` | cusip, quarter, holder | immutable per quarter |
| `insider_trade` | accession, line_no | immutable |
| `filing` | accession | immutable |
| `rating_month` | symbol, month | immutable except the current month |
| `snapshot` | resource, key, fetched_at (JSON payload) | snapshot: profile, peers, earnings date, identifier maps |
| `fetch_log` | resource, key | last success, last attempt, covered through, next due |

Bulk SEC files (13F about 100 MB and N-PORT about 441 MB per quarter) are streamed by a scheduled job, and we keep only rows for symbols we track. The raw zips are never stored.

**Size, for a universe of 500 symbols:** prices 500 × 20 yrs × 252 days ≈ 2.5 M rows ≈ 250 MB with indexes. Statements ≈ 0.5 M facts. Everything else is small once filtered. The total stays under 1 GB.

## 5. Hosting

Decision (2026-11-21): **Prisma Postgres** for the database, **Render** for the Java backend, **Vercel** for the frontend.

- The backend uses plain JDBC and Flyway, not the Prisma ORM. It connects through Prisma Postgres's direct TCP connection string (`DATABASE_URL`). Use the pooled string if the direct one hits connection limits.
- **Check the free-plan limits before seeding [K, verify]:** storage (about 500 MB to 1 GB) and a monthly cap on database operations. Every query counts, so the Caffeine layer and batched inserts matter. Size the seed universe to fit the storage cap.
- Render's free web service sleeps after about 15 minutes without traffic and cold-starts on the next request. The refresh design below uses that instead of fighting it.

## 6. Seed on first run

On the first boot with an empty `fetch_log`, a background job stores a seed universe, so the first visitor already sees data. Everything else loads on demand.

**Universe (about 70 symbols)**, kept in a resource file so it can change without code:

| Group | Symbols | Why |
|---|---|---|
| Benchmarks | SPY, QQQ, DIA, IWM, VTI | beta and alpha baselines, the most-held index funds |
| Core funds | VOO, IVV, VEA, VWO, AGG, BND, TLT, GLD, VNQ, SCHD | the funds most retail portfolios hold; bonds, gold and REITs for diversification |
| Sector SPDRs | XLK, XLF, XLV, XLE, XLY, XLP, XLI, XLU, XLB, XLRE, XLC | sector exposure and peer baselines |
| Mega caps | AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, AVGO, BRK.B, LLY | the largest weights in SPY and QQQ, the most looked-up tickers |
| Popular large caps | JPM, V, MA, UNH, XOM, JNJ, WMT, PG, HD, COST, NFLX, AMD, KO, PEP, BAC, ORCL, CRM, PLTR, INTC, DIS, ABBV, MRK, CVX, ADBE, CSCO, MCD, T, PFE, NKE, BA, SBUX, PYPL, UBER, COIN, SOFI | high retail search and ownership interest (a judgement call; edit freely) |

**Datasets per seed symbol:**

| Data | Depth | Calls |
|---|---|---|
| Raw prices + dividends + splits | 10 years | 1 per symbol (Tiingo) |
| Profile and sector | current | 1 per symbol (SEC `submissions`) |
| Statements | all XBRL history (about 2009+) | 1 per stock (SEC `companyfacts`; funds skipped) |
| Peers | current | 1 per stock (Finnhub) |
| ETF holdings | latest quarter | 1 per fund: that fund's own latest NPORT-P filing, not the 441 MB bulk set |

**Shared series (once):** 3-month bill and 10-year yields (20 years), CPI, unemployment, real GDP, fed funds, NBER recession dates, French factors and Shiller (full history), WTI and Brent (20 years).

**Not seeded (loaded on demand or skipped):**
- Institutional holders. 13F is a bulk-only dataset (about 100 MB per quarter), too heavy for a seed on a free instance. It is built the first time a user opens that view, for the seed universe only.
- Insiders, filings and ratings. These are cheap per symbol, so they load on first view.
- Global macro and trade flows. They are only needed when a stress scenario uses them.

**Budget:** about 70 Tiingo symbols (of 500 a month), about 120 SEC calls (at 10/s, seconds), about 55 Finnhub calls (at 60/min, about 1 minute). Storage is about 70 × 10 × 252 ≈ 180k price rows plus about 0.1 M statement facts, well under 100 MB.

## 7. Refresh on visit, no cron

Low traffic makes always-on schedulers a waste. Refresh work runs only when someone is using the app.

1. **Wake-up check.** A visit wakes the Render instance. On `ApplicationReadyEvent`, one background task reads `fetch_log` for the seed universe and shared series, and refreshes whatever is past its `next_due`. On the first run this is the seed.
2. **Stale-while-revalidate on each request.** A request for a resource and key:
   - inside fresh TTL → serve it;
   - past TTL but inside max stale → serve it now, with the stale flag, and queue a background refresh;
   - nothing stored → fetch synchronously through the waterfall.
3. **Single flight.** Before refreshing a resource and key, the task takes a Postgres advisory lock on that pair. Two visitors (or two instances) never fetch the same thing twice.
4. **Per-source budgets.** Each source has a token bucket for its rate limit and a daily or monthly counter in the database (Tiingo symbols per month, Alpha Vantage 25 per day). An empty budget makes the waterfall skip that layer, as if it were down.
5. **Resumable.** Progress is written to `fetch_log` per key, so if Render puts the instance to sleep mid-job, the next visit continues where it stopped. Nothing depends on a job finishing in one run.
6. **Bounded.** Background refreshes run on a small fixed pool (2 threads), so a burst of visits cannot starve request handling or the database operation quota.

The cost of this design: the first visitor after a long idle period may see stale-flagged data for a minute while the refresh runs. For a demo that is the right trade.
