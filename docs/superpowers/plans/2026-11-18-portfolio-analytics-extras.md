# Portfolio Analytics Extras Implementation Plan (risk-management-ms)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Every task is TDD (superpowers:test-driven-development): write the failing test, watch it fail, write the minimum code, watch it pass.

**Goal:** Add six read-only analytics endpoints to FinRisk: correlation, drawdown, alpha, downside exposure, ETF look-through, ETF overlap.

**Repo / branch:** `risk-management-ms/` (its own git repo), branch `feature/portfolio-analytics-extras`, cut from `main`.

## Global Constraints

- Java 21, Spring Boot 3.3, plain JDBC (no JPA). Package `com.finrisk`. Follow `BetaService` / `BetaServiceTest` as the pattern: Mockito unit tests (`@ExtendWith(MockitoExtension.class)`), AssertJ, constructor injection, response DTOs are Java records in `com.finrisk.dto.response`.
- Routes: `GET /api/v1/accounts/{accountId}/<name>`, added to the existing `PortfolioController` (new service injected into its constructor).
- Unknown account → `AccountNotFoundException("Account not found")` (the existing handler turns it into 404). Empty portfolio (no holdings) → a well-formed response with empty lists and `null` metrics, not an error.
- Price data uses the same approach as `BetaService`: last 90 days (`PRICE_DAYS = 90`), asset history from `AssetPriceHistoryDao.latestPrices(assetId, 90)` (newest first, reverse it), benchmark `SPY` from `MarketDataProvider.fetchDailyPrices("SPY", 90)` (newest first, reverse it). Series are aligned by position, not date, **at the newest end** (when lengths differ, keep the most recent n entries of every series, not the oldest n; decided after the final review, 2026-11-18). Do not touch `BetaService` (it keeps the old oldest-end behaviour; separate follow-up).
- Returns are log returns. Weights are `currentValue / sum(currentValue)` over holdings (cash excluded), as in `BetaService`. Annualisation factor is 252.
- Fewer than 5 return samples (`MIN_SAMPLES = 5`) → the metric is `null` (not 1.0).
- Only unit tests. Do NOT write `*IT.java` (they need SQL Server). Verify with `mvn -B test` from `risk-management-ms/`.
- Do NOT modify `openapi.yaml` / `openapi.json` (they have unrelated uncommitted edits). Do NOT commit `target/`. Commit only the files you create or change for your task, using `git add <paths>`, never `git add -A` or `git commit -a`.
- Commit message style: `feat: add <what> endpoint GET /api/v1/accounts/{id}/<name>`.

---

### Task 1: Shared helpers `ReturnsMath` and `PortfolioPrices`

**Files:** create `src/main/java/com/finrisk/util/ReturnsMath.java`, `src/main/java/com/finrisk/service/PortfolioPrices.java`; tests `src/test/java/com/finrisk/util/ReturnsMathTest.java`, `src/test/java/com/finrisk/service/PortfolioPricesTest.java`.

`ReturnsMath` (final class, static methods, no state):
- `double[] logReturns(List<Double> pricesOldestFirst)` — `ln(p[i]/p[i-1])`, length n-1; empty array if fewer than 2 prices.
- `double mean(double[] a)`; `double stdDev(double[] a)` (sample, n-1; 0.0 if n<2); `double covariance(double[] a, double[] b)` (sample, over `min(len)`); `Double correlation(double[] a, double[] b)` (Pearson over `min(len)`; `null` if either stdDev is 0 or fewer than 2 samples).
- `double[] weightedSum(double[][] seriesPerHolding, double[] weights)` — element-wise `Σ w_i * series_i[t]` over the shortest series length.

`PortfolioPrices` (`@Component`, constructor `(PortfolioDao, AssetPriceHistoryDao, MarketDataProvider)`):
- `List<Holding> requireHoldings(long accountId)` — throws `AccountNotFoundException("Account not found")` when `portfolioDao.cashBalance(accountId)` is empty, else `portfolioDao.holdings(accountId)`.
- `double[] weights(List<Holding> holdings)` — value weights; all zeros if total is 0.
- `List<Double> assetPricesOldestFirst(long assetId)` and `List<Double> benchmarkPricesOldestFirst()` (SPY).
- Constants `BENCHMARK = "SPY"`, `PRICE_DAYS = 90`, `MIN_SAMPLES = 5` exposed as `public static final`.

Tests: hand-computed values for each `ReturnsMath` function (including the null/empty edge cases above); `PortfolioPrices` account-not-found, weights, and the reverse-to-oldest-first behaviour with mocks.

### Task 2: Correlation — `GET /correlation`

**Files:** `dto/response/CorrelationResponse.java`, `service/CorrelationService.java`, edit `controller/PortfolioController.java`; test `service/CorrelationServiceTest.java`.

`record CorrelationResponse(long accountId, List<String> symbols, List<List<Double>> matrix, Double averagePairwiseCorrelation)`.
- `symbols` = holding symbols in holdings order; `matrix[i][j]` = Pearson correlation of the two holdings' log returns; diagonal is 1.0; an entry is `null` when the correlation is undefined (fewer than 5 samples or zero variance).
- `averagePairwiseCorrelation` = mean of the non-null off-diagonal upper-triangle entries; `null` if there are none (fewer than 2 holdings, or all undefined).
- Empty portfolio → `symbols` and `matrix` empty, average `null`.

Tests: perfectly correlated pair → 1.0; perfectly inverse pair → -1.0; three holdings give a symmetric 3x3 matrix with 1.0 diagonal; constant-price holding → null entries and excluded from the average; single holding → average null; account not found; empty portfolio.

### Task 3: Drawdown — `GET /drawdown`

**Files:** `dto/response/DrawdownResponse.java`, `dto/response/HoldingDrawdown.java`, `service/DrawdownService.java`, edit controller; test `service/DrawdownServiceTest.java`.

`record HoldingDrawdown(long assetId, String symbol, Double maxDrawdown)`; `record DrawdownResponse(long accountId, Double maxDrawdown, Double currentDrawdown, List<HoldingDrawdown> holdings)`.
- Drawdowns are non-positive fractions (e.g. `-0.12` = 12% below the running peak).
- Per holding: from the price series, `min over t of (price_t / runningPeak_t - 1)`; `null` if fewer than 2 prices.
- Portfolio: build the weighted log-return series (`ReturnsMath.weightedSum`), accumulate to a value index starting at 1.0 (`index_t = index_{t-1} * exp(r_t)`, include the starting 1.0 as the first peak), then `maxDrawdown` = minimum of `index/peak - 1` and `currentDrawdown` = the last such value. `null` when fewer than 5 return samples.
- Empty portfolio → `maxDrawdown`/`currentDrawdown` null, `holdings` empty.

Tests: a series that rises then falls 20% gives maxDrawdown ≈ -0.20 and currentDrawdown equal to it; a monotonic rising series gives 0.0; recovery after the trough gives currentDrawdown 0.0 but maxDrawdown unchanged; per-holding values; fewer than 5 samples → null; account not found; empty portfolio.

### Task 4: Alpha — `GET /alpha`

**Files:** `dto/response/AlphaResponse.java`, `service/AlphaService.java`, edit controller; test `service/AlphaServiceTest.java`.

`record AlphaResponse(long accountId, Double alpha, Double portfolioReturn, Double benchmarkReturn, double beta, double riskFree, String benchmark)`.
- Query parameter `riskFree` (annual, decimal, default `0.0`, `@RequestParam(defaultValue = "0.0")`), passed to `AlphaService.computeAlpha(long accountId, double riskFree)`.
- `portfolioReturn` = `mean(portfolio daily log returns) * 252`; `benchmarkReturn` = `mean(SPY daily log returns) * 252`; `beta` = `BetaService.computeBeta(accountId).portfolioBeta()` (reuse, inject `BetaService`).
- `alpha = portfolioReturn - (riskFree + beta * (benchmarkReturn - riskFree))` (Jensen's alpha, annualised).
- Fewer than 5 samples or empty portfolio → `alpha`, `portfolioReturn`, `benchmarkReturn` are null (beta from `BetaService` still reported; `1.0` when no holdings).

Tests: with beta mocked/known and hand-computed returns, alpha matches the formula; riskFree changes the result as the formula says; portfolio identical to SPY with beta 1.0 gives alpha ≈ 0; account not found; insufficient data → nulls.

### Task 5: Downside exposure — `GET /downside`

**Files:** `dto/response/DownsideResponse.java`, `service/DownsideService.java`, edit controller; test `service/DownsideServiceTest.java`.

`record DownsideResponse(long accountId, Double downsideDeviation, Double sortinoRatio, Double downsideBeta, Double worstDay, String benchmark)`.
- Portfolio daily log returns `rp` as in Task 3.
- `downsideDeviation` (annualised) = `sqrt( Σ min(rp_t, 0)^2 / n ) * sqrt(252)`, target return 0, n = all samples.
- `sortinoRatio` = `(mean(rp) * 252) / downsideDeviation`; `null` if downsideDeviation is 0.
- `downsideBeta` = over only the days where the SPY return `rm_t < 0`: `covariance(rp, rm) / variance(rm)` on those days; `null` if fewer than 5 such days or variance 0.
- `worstDay` = `min(rp)` (a negative or zero fraction).
- Fewer than 5 samples or empty portfolio → all four metrics null.

Tests: hand-computed downsideDeviation for a small series; all-positive returns → downsideDeviation 0.0, sortino null; downsideBeta of a portfolio that is 2x SPY on down days ≈ 2.0; fewer than 5 down days → null; worstDay; account not found; empty portfolio.

### Task 6: ETF look-through — `GET /etf-look-through`

**Files:** create `marketdata/EtfHolding.java`; edit `marketdata/MarketDataProvider.java`, `marketdata/fmp/FmpMarketDataProvider.java` (and its existing test `marketdata/fmp/FmpMarketDataProviderTest.java`); create `dto/response/LookThroughResponse.java`, `service/EtfLookThroughService.java`; edit controller; test `service/EtfLookThroughServiceTest.java`.

- `record EtfHolding(String symbol, String name, BigDecimal weight)` — `weight` is a fraction (0.071 = 7.1%).
- New interface method `List<EtfHolding> fetchEtfHoldings(String etfSymbol)`: never throws, returns an empty list on unknown symbol / missing key / network error (same contract as `fetchDailyPrices`). Implement in `FmpMarketDataProvider` by calling FMP `GET {base-url}/etf-holder/{symbol}`, mapping `asset` → symbol, `name` → name, `weightPercentage` (percent) → weight fraction (divide by 100). Follow exactly how `fetchProfile` makes its request and how `FmpMarketDataProviderTest` mocks it. Any other class implementing `MarketDataProvider` (including test fakes) must be updated to compile.
- An ETF holding is a `Holding` whose asset type is `ETF` (inspect `Holding` / `AssetType`).
- `record LookThroughResponse(long accountId, BigDecimal totalValue, List<Exposure> exposures, List<String> unresolvedEtfs)` with nested `record Exposure(String symbol, String name, double effectiveWeight, double directWeight, double viaEtfWeight, List<Source> sources)` and `record Source(String etf, double weight)`. Nested records live inside `LookThroughResponse`.
- `effectiveWeight = directWeight + viaEtfWeight`. A direct (non-ETF) holding contributes its value weight to `directWeight`. An ETF holding with portfolio weight `w` and underlying weight `u` contributes `w * u` to `viaEtfWeight` and one `Source(etfSymbol, w * u)`. Same underlying reached from several ETFs sums up. `exposures` sorted by `effectiveWeight` descending.
- An ETF for which `fetchEtfHoldings` returns an empty list is listed in `unresolvedEtfs` and its own weight is shown as a direct exposure under the ETF's own symbol, so total effective weight still sums to ~1.
- `totalValue` = sum of holding `currentValue`.

Tests: stock + ETF where the ETF holds the same stock → effective weight is the sum, with both `directWeight` and `viaEtfWeight` correct and the source listed; two ETFs sharing a stock; unresolved ETF falls back as direct exposure and is reported; effective weights sum to ~1.0; sorted descending; account not found; empty portfolio. In the FMP provider test: parses a sample response (percent → fraction) and returns an empty list on error.

### Task 7: ETF overlap — `GET /etf-overlap`

**Files:** `dto/response/OverlapResponse.java`; edit `service/EtfLookThroughService.java` (add method) and controller; extend `EtfLookThroughServiceTest`.

`record OverlapResponse(long accountId, List<Pair> pairs, List<String> unresolvedEtfs)` with nested `record Pair(String etfA, String etfB, double overlap, List<String> sharedHoldings)`.
- For every unordered pair of distinct ETFs held in the account (resolved ones only), `overlap = Σ over shared symbols of min(weightA, weightB)` using each ETF's own underlying weights (a fraction in 0..1); `sharedHoldings` = the shared symbols sorted by `min(weightA, weightB)` descending.
- Pairs sorted by `overlap` descending. Fewer than 2 resolved ETFs → `pairs` empty. ETFs with no data go to `unresolvedEtfs`.
- Reuse the holdings-fetch helper from Task 6 (fetch each ETF once per request); do not duplicate it.

Tests: two ETFs with a known overlap (hand-computed); identical ETFs → 1.0; disjoint ETFs → 0.0 with no shared holdings; three ETFs give 3 pairs sorted; unresolved ETF excluded and reported; single ETF → no pairs; account not found.
