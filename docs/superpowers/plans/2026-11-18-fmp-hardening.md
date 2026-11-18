# FMP Hardening and Input Bounds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Every task is TDD (superpowers:test-driven-development): write the failing test, watch it fail for the right reason, minimal code, watch it pass. A test that already passes on existing code must be proven to bite by temporarily mutating production code, seeing it fail, and reverting exactly.

**Goal:** Fix pre-existing robustness issues that the final reviews of the two feature branches found but left out of scope.

**Repos / branches (own git repos; commit on the existing, unmerged, unpushed feature branches):**
- Tasks 1, 2: `risk-management-ms/`, branch `feature/portfolio-analytics-extras` (HEAD dc2dca3).
- Tasks 3, 4: `sector-valuation-ms/`, branch `feature/ddm-lynch-fair-value` (HEAD f8c85f9).

## Global Constraints

- Commit only your own files via `git add <paths>`, never `git add -A` / `git commit -a`. Never commit `target/`, `coverage/`, `.env`, `openapi.yaml`, `openapi.json` (risk-management-ms has unrelated uncommitted edits to the openapi files). No push.
- risk-management-ms: Java 21, Spring Boot 3.3, Mockito/AssertJ unit tests only (no `*IT.java`). Verify with `mvn -B test`.
- sector-valuation-ms: Node 20+, ESM, jest. Always run jest with `--forceExit` until Task 4 is done (e.g. `npm test -- --forceExit`).
- Do not change behaviour beyond what the task states; each task's tests must pin the new behaviour.
- Commit trailer: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

---

### Task 1: Harden `FmpMarketDataProvider` (risk-management-ms)

**Files:** `src/main/java/com/finrisk/marketdata/fmp/FmpMarketDataProvider.java`, test `src/test/java/com/finrisk/marketdata/fmp/FmpMarketDataProviderTest.java` (it already uses a local JDK `HttpServer`; follow its style).

Applies to all three methods `fetchDailyPrices`, `fetchProfile`, `fetchEtfHoldings`. Their public contracts (never throw; empty list / default profile on failure) do not change.

1. **Encode the symbol** in the URL path (and wherever the symbol is put in the URL): `URLEncoder.encode(symbol, StandardCharsets.UTF_8)` then replace `+` with `%20` (URLEncoder is for form encoding; this is a path segment). A symbol like `BRK B` or `../x` must no longer throw from `URI.create` and must not alter the path structure. Implement it once in a small private helper used by all three methods, not three copies.
2. **Never log `e.getMessage()`** of a failed request (it can contain the full URL including `apikey=`, and is `null` for `ConnectException`). Log the exception class (`e.getClass().getSimpleName()`) and the symbol only. Also make sure no log line contains the API key or a full request URL, including the non-200 path.
3. **Timeouts:** set a connect timeout on the `HttpClient` (5 seconds) and a request timeout on every `HttpRequest` (10 seconds), as named constants.
4. **`fetchEtfHoldings` row handling:** a single row with a missing/blank `asset`, a missing/null `weightPercentage`, or a non-numeric `weightPercentage` is SKIPPED; the other rows are still returned (today one non-numeric weight throws inside the loop and the catch-all returns an empty list for the whole ETF). A top-level body that is not an array returns an empty list.

Tests (each failing first): the symbol `BRK B` is requested as `BRK%20B` (assert on the path the local `HttpServer` receives) and `../x` cannot escape the path (the server sees an encoded segment); a failing request (connection refused) logs without the apikey and without `null` message text (capture the log output via the logging framework the project already uses in tests, or if that is impractical assert the behaviour through a small package-private log-message helper you introduce and test; say which you chose); a server that never responds is cut off by the request timeout (make the timeout injectable through a package-private constructor or a field so the test can use a short value — keep the production defaults 5 s / 10 s); `fetchEtfHoldings`: non-200 → empty list, malformed JSON → empty list, non-array body → empty list, row missing `asset` skipped, row with null `weightPercentage` skipped, row with `"abc"` weight skipped while the valid rows are returned, percent → fraction still correct (7.1 → 0.071).

### Task 2: `BetaService` tail alignment (risk-management-ms)

**Files:** `src/main/java/com/finrisk/service/BetaService.java`, test `src/test/java/com/finrisk/service/BetaServiceTest.java`. (`BetaService` was off-limits earlier; this task explicitly authorises changing it.)

`computeHoldingBeta` currently takes `subList(0, n+1)` of both the asset prices and the SPY prices (both oldest-first), i.e. it keeps the OLDEST n+1 entries, so when the two histories have different lengths the two return series are compared on different dates. Change it to align at the NEWEST end, like the new analytics services do (see `util/ReturnsMath.tail(double[], int)` and how `DownsideService` / `AlphaService` use it): compute log returns of each full series, cut both return series to their common length keeping the LAST entries, then compute beta as before. Keep everything else identical: the `MIN_SAMPLES` check and its 1.0 fallback (`n < MIN_SAMPLES` where n is the common return count, same threshold as today), the zero-variance → 1.0 fallback, the weighting, the empty-portfolio and unknown-account behaviour, and the response shape. All existing `BetaServiceTest` expectations must stay valid unchanged (their series have equal lengths); if one needs editing, stop and report why.

Tests (failing first): an asset with 8 prices against SPY with 6 prices whose tail-aligned beta differs from the head-aligned beta — pick values so the tail-aligned beta is a hand-computed exact number (e.g. the asset's last 5 returns are exactly 2x the SPY returns → beta 2.0, while its older returns are unrelated so head alignment gives something else); show the arithmetic in a comment; and the mirror case with SPY longer than the asset history.

### Task 3: Ticker and loop bounds for the existing schemas (sector-valuation-ms)

**Files:** `src/validation/schemas.js`, test `tests/validation/schemas.test.js` (and route tests only if an existing assertion breaks).

1. `AnalyzeSchema`, `DcfSchema`, `CompareSchema` use `z.string().min(1).max(10).transform(upper)` for `ticker`. Switch all three to the shared `SafeTicker` already defined in the file for `DdmSchema`/`LynchSchema` (`/^[A-Za-z0-9.\-]{1,10}$/`, upper-cased). This is a deliberate behaviour change: `../v4/x?`, `AAPL/..`, `A B`, empty and 11-character tickers are now rejected with 400; `BRK.B` and `aapl` are accepted (upper-cased). Say so in the commit message.
2. Bound the unbounded loop inputs that `computeDCF` iterates: `projectionYears` in `DcfSchema` and `CompareSchema`, and `StageSchema.years` (used by both). Add `.max(100)`. Also check `buildStages` in `src/services/stats.js` for any other loop driven by user input and report it (do not change it unless it is the same unbounded-loop problem with a user-supplied count).

Tests (failing first): each of the three schemas rejects the bad tickers above and accepts `BRK.B`/`aapl`; `projectionYears` 100 accepted and 101 rejected for `DcfSchema` and `CompareSchema`; a stage with `years: 101` rejected, `years: 100` accepted. Existing route tests (`tests/routes/analyze.test.js`, `dcf.test.js`, `compare.test.js`) must still pass; fix a fixture only if it used an invalid ticker, and say so.

### Task 4: Stop `tests/app.test.js` leaving jest hanging (sector-valuation-ms)

**Files:** `tests/app.test.js` only (plus `src/app.js` only if it is impossible otherwise — prefer not).

`tests/app.test.js` calls `createApp()` with no stub cache, so `new RedisCache(...)` opens a real ioredis connection to 127.0.0.1:6379 that is never closed, and a full `npm test` does not exit by itself (confirmed with `--detectOpenHandles`: one TCPWRAP from `src/cache/redis.js` ← `createApp` ← `tests/app.test.js`). Pass a stub `cache` (and a stub `marketData` if needed) to `createApp({ marketData, cache })` the way the route tests do, so no real connection is opened.

Done when `npm test` (WITHOUT `--forceExit`) runs the whole suite and the process exits on its own within a few seconds, with all tests passing — run it with a `timeout 120` wrapper and report the exit code and duration. Then run `npm test -- --detectOpenHandles` and confirm it reports no open handles. The test's own assertions (what it verifies about the app, e.g. `/health`) must stay equivalent; if the only thing it verified was via the real cache, say so.
