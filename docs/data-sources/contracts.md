# Data contracts: objectives, canonical schemas, layer overlap

Status: design, 2026-11-21. Builds on `inventory.md` (who supplies what) and `waterfall.md` (layer order).

Native field names come from the providers' documented responses as I know them **[K]**. Each adapter pins them with a recorded-fixture test before it ships, so a wrong name fails a test, not production.

## 1. Objectives decide the fields

We store only the fields a decision uses. A field with no decision behind it is not modelled, even when every source offers it.

| # | Objective (decision it supports) | Computation | Minimal input |
|---|---|---|---|
| O1 | How risky is the portfolio? | log returns, volatility, beta, alpha, correlation, drawdown, downside | daily total-return-adjusted close, risk-free rate |
| O2 | What am I really exposed to? | sector mix, ETF look-through, overlap | sector, asset type, ETF constituents and weights |
| O3 | Is the business healthy? | margins, ROE, leverage, liquidity, cash conversion | about 15 statement line items |
| O4 | What is it worth? | DCF, DDM, Lynch, peer multiples | FCF, shares, EPS history, dividends, price, net debt, EBITDA, peers |
| O5 | What breaks it? | factor shocks, historical scenario replay | macro, commodity, factor and trade series, recession dates |
| O6 | What do insiders and the street signal? | net insider buying, institutional change, rating trend, next earnings | insider trades, 13F positions, recommendation counts, earnings date |

Notation below: `field*` = **required** (the record is rejected without it), `field` = optional (missing means the dependent metric is skipped).
Layer cells: ✓ maps directly, ⇄ maps through an adapter, ∑ derived from other fields, — missing (skip).

## 2. Resources

### Risk

**prices** → `PricePoint(date*, adjClose*)` (O1)

| Canonical | 1 Alpaca `bars?adjustment=all` | 2 Tiingo `daily/{s}/prices` | 3 Yahoo `v8/chart` |
|---|---|---|---|
| date* | ⇄ `t` (RFC 3339) | ⇄ `date` | ⇄ `timestamp[i]` (epoch) |
| adjClose* | ✓ `c` (adjusted by request) | ✓ `adjClose` | ✓ `indicators.adjclose[0].adjclose[i]` |
| ignored | o h l v n vw | open high low close volume adj* splitFactor | open high low close volume |

Overlap is total on what we need. Stooq is **removed**: its CSV close is split-adjusted only, so it cannot supply `adjClose*` with the same meaning. Tiingo's `divCash` is read by the dividends adapter, not here.

**sector** → `CompanyProfile(symbol*, name*, sector*, assetType*, industry)` (O2). Adds `assetType` (STOCK, ETF, FUND) to today's record, because look-through must know which holdings are funds.

| Canonical | 1 SEC `submissions/CIK.json` | 2 Finnhub `stock/profile2` | 3 Yahoo `quoteSummary` |
|---|---|---|---|
| symbol* | ✓ `tickers[0]` | ✓ `ticker` | ✓ request |
| name* | ✓ `name` | ✓ `name` | ✓ `price.longName` |
| sector* | ⇄ `sic` → SectorTaxonomy | ⇄ `finnhubIndustry` → SectorTaxonomy | ⇄ `assetProfile.sector` → SectorTaxonomy |
| assetType* | ⇄ fund if ticker is in `company_tickers_mf.json`, else STOCK | — | ✓ `quoteType.quoteType` |
| industry | ✓ `sicDescription` | ✓ `finnhubIndustry` | ✓ `assetProfile.industry` |

Overlap exists, but three taxonomies (SIC, Finnhub, Yahoo) disagree. **One adapter, `SectorTaxonomy`, maps all three to one 11-sector enum.** Finnhub has no asset type, so the waterfall treats a Finnhub profile as incomplete for an ETF and moves on.

**etf_holdings** → `FundHoldings(etf*, asOf*, coverage*, holdings: List<EtfHolding(symbol*, weight*, name)>)` (O2). `coverage` = sum of weights, so a top-10 list is visibly partial.

| Canonical | 1 SEC N-PORT bulk (`FUND_REPORTED_HOLDING`) | 2 Issuer CSV (iShares-style) | 3 Yahoo `topHoldings` |
|---|---|---|---|
| asOf* | ✓ `REPORT_DATE` | ✓ file header date | — (use fetch date) |
| symbol* | ⇄ `ISSUER_CUSIP` → OpenFIGI → ticker | ✓ `Ticker` | ✓ `holdings[].symbol` |
| weight* | ⇄ `PERCENTAGE` / 100 | ⇄ `Weight (%)` / 100 | ✓ `holdingPercent` |
| name | ✓ `ISSUER_NAME` | ✓ `Name` | ✓ `holdingName` |
| coverage* | ∑ ≈ 1.0 | ∑ ≈ 1.0 | ∑ ≈ 0.2–0.5 |

N-PORT has no ticker; `IdentifierResolver` (OpenFIGI plus SEC ticker files, cached forever) supplies it. Rows that do not resolve (bonds, cash, swaps) are dropped and lower `coverage`.

**risk_free** → `RatePoint(date*, tenor*, rate*)` (O1), `rate` as a decimal.

| Canonical | 1 Treasury daily par yield CSV | 2 FRED `DGS3MO` |
|---|---|---|
| date* | ✓ `Date` | ✓ `observations[].date` |
| rate* | ⇄ `"3 Mo"` percent → decimal | ⇄ `value` percent → decimal; `"."` = missing, skip the row |

Massive is removed: two years of history, and its fields duplicate Treasury's.

### Fundamentals

**statements** → `FinancialStatement(periodEnd*, periodType* (FY, Q), filed*, items: Map<LineItem, BigDecimal>)` (O3, O4)

Minimal `LineItem` set: REVENUE*, NET_INCOME*, OPERATING_CASH_FLOW*, CAPEX*, OPERATING_INCOME, GROSS_PROFIT, DEPRECIATION, INTEREST_EXPENSE, TOTAL_ASSETS, TOTAL_LIABILITIES, EQUITY, CASH, TOTAL_DEBT, CURRENT_ASSETS, CURRENT_LIABILITIES, EPS_DILUTED, SHARES_DILUTED, DIVIDENDS_PER_SHARE. EBITDA is derived (OPERATING_INCOME + DEPRECIATION), never stored.

| Canonical | 1 SEC `companyfacts` | 2 Finnhub `financials-reported` | 3 Yahoo fundamentals timeseries |
|---|---|---|---|
| periodEnd* | ✓ `end` | ✓ `endDate` | ✓ `asOfDate` |
| periodType* | ⇄ `fp` (FY, Q1–Q3; Q4 = FY − Q1..Q3) | ⇄ `quarter` (0 = annual) | ⇄ key prefix `annual`/`quarterly` |
| filed* | ✓ `filed` | ✓ `filedDate` | — (skip: no point-in-time) |
| items | ⇄ `facts.us-gaap.<Tag>.units.USD[].val` | ⇄ `report.{ic,bs,cf}[].concept` + `value` | ⇄ `annualTotalRevenue`, `annualNetIncome`, … `.reportedValue.raw` |

Layers 1 and 2 both carry **us-gaap concept names**, so **one adapter, `UsGaapConcepts`, serves both**. It holds an alias list per line item (REVENUE ← `Revenues` | `RevenueFromContractWithCustomerExcludingAssessedTax` | `SalesRevenueNet`). Yahoo uses its own key names, so it gets a separate alias table. Missing line items are skipped. A statement missing a required item is rejected for that period only.

**ratios** → `Ratios(asOf*, grossMargin, operatingMargin, netMargin, roe, roa, currentRatio, debtToEquity, fcfMargin, interestCoverage)` (O3)

Computed in-house from `statements` plus price, so this is a formula, not a waterfall layer. Finnhub `stock/metric` (`netProfitMarginTTM`, `roeTTM`, `currentRatioQuarterly`, `totalDebt/totalEquityQuarterly`, …) fills only the ratios whose inputs are missing. All fields are optional.

### Valuation

**per-share inputs** → today's `Fundamentals(freeCashFlow, sharesOutstanding, eps, epsGrowth)` (O4)

Derived from `statements`, with no waterfall of its own: FCF = OPERATING_CASH_FLOW − CAPEX, shares ← `dei:EntityCommonStockSharesOutstanding`, eps ← EPS_DILUTED, epsGrowth = CAGR of EPS over the last 3–5 fiscal years. This replaces the separate "fundamentals_per_share" resource.

**dividends** → `Dividend(exDate*, amount*)` (O4: DDM uses the trailing-12-month sum)

| Canonical | 1 Alpaca corporate actions | 2 Tiingo prices | 3 Yahoo `v8/chart?events=div` | 4 SEC `companyfacts` |
|---|---|---|---|---|
| exDate* | ✓ `cash_dividends[].ex_date` | ✓ `date` where `divCash > 0` | ⇄ `events.dividends.*.date` | ⇄ period `end` (no ex-date) |
| amount* | ✓ `rate` | ✓ `divCash` | ✓ `amount` | ✓ `CommonStockDividendsPerShareDeclared` |
| ignored | special foreign record payable | — | — | — |

Layer 4 reports per period, not per payment. That is enough for a trailing-12-month sum, so it stays as the last layer.

**peers** → `Peer(symbol*, name)` (O4). The contract changes from `peers(sector, limit)` to `peers(symbol, limit)`, because neither good source lists by sector.

| Canonical | 1 Finnhub `stock/peers` | 2 SEC SIC index (`submissions.zip` + `company_tickers.json`) |
|---|---|---|
| symbol* | ✓ array element | ✓ `ticker` of companies sharing the subject's `sic` |
| name | — (skip, or resolve through `profile`) | ✓ `title` |

Peer multiples then come from each peer's own `statements` and `prices`, computed in-house.

### Stress

**us_macro** → `MacroSeries(id*, unit*, frequency*, points: List<(date*, value*)>)` (O5). A `SeriesCatalog` maps canonical IDs to each source's code: CPI → BLS `CUUR0000SA0` / FRED `CPIAUCSL`, UNEMPLOYMENT → BLS `LNS14000000` / `UNRATE`, REAL_GDP → BEA NIPA T10106 line 1 / `GDPC1`, T10Y → Treasury `"10 Yr"` / `DGS10`.

| Canonical | 1 BLS v2 | 2 Treasury | 3 FRED |
|---|---|---|---|
| date* | ⇄ `year` + `period` (`M01`) | ✓ `Date` | ✓ `date` |
| value* | ⇄ `value` (string) | ⇄ percent → decimal | ⇄ `value`, `"."` = skip |
| unit, frequency | from SeriesCatalog | from SeriesCatalog | ✓ series metadata |

BEA uses `TimePeriod` (`2024Q3`) and `DataValue` with thousands commas, so its adapter strips the commas. The fed funds rate is in neither BLS nor BEA: the NY Fed markets API (EFFR, free, no key) becomes its first layer, with FRED `FEDFUNDS` second.

**global_macro** → same `MacroSeries`, keyed by `(indicator, country)`.

| Canonical | 1 World Bank v2 | 2 OECD SDMX | 3 IMF SDMX |
|---|---|---|---|
| date* | ✓ `date` (year) | ✓ `TIME_PERIOD` | ✓ `TIME_PERIOD` |
| value* | ✓ `value`, `null` = skip | ✓ `OBS_VALUE` | ✓ `OBS_VALUE` |
| country | ✓ `countryiso3code` | ⇄ `REF_AREA` | ⇄ `REF_AREA` |

**factor_history** → `FactorReturn(month*, factor*, value*)` (O5). There is one source per series, so no fallback: Kenneth French (`Mkt-RF`, `SMB`, `HML`, `RF`, monthly percent, 1926+) and Shiller (`P`, `D`, `E`, `CPI`, `GS10`, monthly, 1871+). These are two different datasets, not overlapping layers.

**recession** → `DateRange(start*, end*)` (O5). Correction: the French and Shiller files carry no recession flag. Layer 1 is the NBER business-cycle table (a short static list, cached as a resource file). Layer 2 is FRED `USREC` (monthly 0/1 runs collapsed into ranges).

**commodities** → `MacroSeries` (O5)

| Canonical | 1 EIA v2 `petroleum/pri/spt` | 2 IMF PCPS | 3 FRED |
|---|---|---|---|
| date* | ✓ `period` | ✓ `TIME_PERIOD` (monthly) | ✓ `date` |
| value* | ✓ `value` | ✓ `OBS_VALUE` | ✓ `value` |
| unit* | ✓ `units` | from catalog | from catalog |

EIA covers energy only (WTI `RWTC`, Brent `RBRTE`, gas). Metals and grains start at IMF PCPS (monthly only).

**trade_flows** → `TradeFlow(year*, reporter*, partner*, flow* (IMPORT, EXPORT), valueUsd*, hsCode)` (O5)

| Canonical | 1 UN Comtrade `data/v1/get/C/A/HS` | 2 IMF DOTS | 3 World Bank |
|---|---|---|---|
| year* | ✓ `refYear` | ✓ `TIME_PERIOD` | ✓ `date` |
| reporter* | ✓ `reporterISO` | ⇄ `REF_AREA` | ✓ `countryiso3code` |
| partner* | ✓ `partnerISO` | ⇄ `COUNTERPART_AREA` | — (world total only) |
| flow* | ⇄ `flowCode` M/X | ⇄ indicator code | ⇄ indicator code |
| valueUsd* | ✓ `primaryValue` | ✓ `OBS_VALUE` | ⇄ % of GDP × GDP |
| hsCode | ✓ `cmdCode` | — (totals only, skip) | — |

World Bank cannot supply `partner*`, so it fails the required check and is **removed** from this waterfall. IMF DOTS has bilateral totals without commodity detail, which is acceptable because `hsCode` is optional.

### Market intelligence

**institutional** → `Holder(holder*, shares*, reportDate*, valueUsd, changeShares)` (O6)

| Canonical | 1 SEC 13F bulk (`INFOTABLE` ⨝ `COVERPAGE`) | 2 Yahoo `institutionOwnership` |
|---|---|---|
| holder* | ✓ `FILINGMANAGER_NAME` | ✓ `organization` |
| shares* | ✓ `SSHPRNAMT` where `SSHPRNAMTTYPE = SH`, `PUTCALL` empty | ✓ `position` |
| reportDate* | ✓ `PERIODOFREPORT` | ✓ `reportDate` |
| valueUsd | ✓ `VALUE` | ✓ `value` |
| changeShares | ∑ against the previous quarter | — (skip) |

13F is keyed by CUSIP; `IdentifierResolver` maps symbol → CUSIP first. Yahoo returns the top 10 only and adds `pctHeld`, which we ignore and compute as shares / sharesOutstanding.

**insiders** → `InsiderTrade(insider*, date*, code*, shares*, acquired*, price, sharesAfter, role)` (O6)

| Canonical | 1 SEC Form 4 bulk | 2 Finnhub `insider-transactions` | 3 Yahoo `insiderTransactions` |
|---|---|---|---|
| insider* | ✓ `RPTOWNERNAME` | ✓ `name` | ✓ `filerName` |
| date* | ✓ `TRANS_DATE` | ✓ `transactionDate` | ✓ `startDate` |
| code* | ✓ `TRANS_CODE` (P, S, A, M…) | ✓ `transactionCode` | — (free text only) |
| shares* | ✓ `TRANS_SHARES` | ⇄ `abs(change)` | ✓ `shares` |
| acquired* | ✓ `TRANS_ACQUIRED_DISP_CD` A/D | ⇄ sign of `change` | — |
| price | ✓ `TRANS_PRICEPERSHARE` | ✓ `transactionPrice` | ⇄ `value / shares` |
| sharesAfter | ✓ `SHRS_OWND_FOLWNG_TRANS` | ✓ `share` | — |
| role | ✓ `RPTOWNER_RELATIONSHIP` | — (skip) | ✓ `filerRelation` |

Yahoo has no transaction code, so it fails `code*` and is **removed** (parsing free text is guesswork). Net insider buying uses code P (open-market purchase) against S (sale) only.

**filings** → `Filing(form*, filed*, accession*, url*, periodOfReport)` (O6)

| Canonical | 1 SEC `submissions` `filings.recent` (columnar arrays) | 2 Finnhub `stock/filings` |
|---|---|---|
| form* | ✓ `form[i]` | ✓ `form` |
| filed* | ✓ `filingDate[i]` | ✓ `filedDate` |
| accession* | ✓ `accessionNumber[i]` | ✓ `accessNumber` |
| url* | ∑ archive path + `primaryDocument[i]` | ✓ `reportUrl` |
| periodOfReport | ✓ `reportDate[i]` | — |

**ratings** → `RecommendationTrend(month*, strongBuy*, buy*, hold*, sell*, strongSell*)` (O6)

| Canonical | 1 Finnhub `stock/recommendation` | 2 Yahoo `recommendationTrend.trend` |
|---|---|---|
| month* | ✓ `period` (date) | ⇄ `period` (`0m`, `-1m` → month relative to fetch date) |
| counts* | ✓ `strongBuy buy hold sell strongSell` | ✓ same names |

Full overlap: one record type, two thin mappers.

**earnings_calendar** → `EarningsEvent(symbol*, date*, timing)` (O6). The contract becomes `nextEarnings(symbol)`, because the portfolio asks per holding, not per date range.

| Canonical | 1 Yahoo `calendarEvents` | 2 Finnhub `calendar/earnings?symbol=` | 3 Alpha Vantage `EARNINGS_CALENDAR` |
|---|---|---|---|
| date* | ⇄ `earnings.earningsDate[0]` | ✓ `date` | ✓ `reportDate` |
| timing | — | ✓ `hour` (bmo/amc) | — |
| ignored | estimates | `epsEstimate`, `revenueEstimate` | `estimate` |

Estimates are out of scope, so they are ignored even though every layer has them.

**news_sentiment**: recommended for **removal**. GDELT `timelinetone` supplies `date` and `tone`, but its fallback Tiingo news has headlines with no sentiment score, so it fails `tone*`. That leaves one D-grade source for an objective (O6) that the other signals already cover.

## 3. Rules the waterfall follows

1. **A layer's answer counts only if every required field is present.** Required fields are enforced in the canonical record's constructor; adapters drop rows that fail; a layer whose rows all fail returns empty, and the waterfall moves to the next layer.
2. **Optional fields missing → `null`.** The domain skips the metric that needs them and says so in the response. It never invents a value.
3. **No field-level mixing across layers.** One answer comes from one layer, because mixing (for example, Alpaca prices with Tiingo dates) breaks consistency. Joins happen only in the domain (statements + price → multiples).
4. **Extra fields are ignored.** A field enters a canonical record only when a decision needs it.
5. **Overlap is handled once.** Shared adapters exist where several layers speak the same vocabulary: `UsGaapConcepts` (SEC, Finnhub), `SectorTaxonomy` (SIC, Finnhub, Yahoo), `IdentifierResolver` (ticker ↔ CUSIP ↔ CIK), `SeriesCatalog` (canonical macro ID ↔ each source's code).

## 4. Interface design

```text
marketdata-api  (what the domain sees; pure Java, no vendors)
  PriceData        daily(symbol, from, to), riskFree(tenor, from, to)
  ReferenceData    profile(symbol), peers(symbol, limit), holdings(etf)
  FundamentalsData statements(symbol, periodType, years), dividends(symbol, from, to)
  MacroData        series(id, from, to), country(indicator, iso3, from, to),
                   factors(model, from, to), recessions(), trade(reporter, partner, hs, year)
  SignalsData      institutional(symbol), insiders(symbol, since), filings(symbol, forms, limit),
                   recommendations(symbol), nextEarnings(symbol)
  + canonical records (PricePoint, CompanyProfile, FundHoldings, FinancialStatement, ...)

marketdata  (adapters; the domain never imports this)
  source/Source                 name(), available()
  source/<Capability>Feed       one per resource, e.g. PriceFeed.daily(...)
                                returns empty = "no data", throws SourceUnavailableException = "broken now"
  Waterfall<F extends Source>   ordered layers for ONE resource:
                                  <T> Optional<T> first(Function<F, Optional<T>> call)
                                  <T> List<T>     firstList(Function<F, List<T>> call)
                                skips unavailable layers, logs each fall-through, never throws
  WaterfallMarketData           implements all five *Data ports; holds one Waterfall per resource
  CachingMarketData             wraps it; per-resource TTL (prices daily, 13F quarterly, NBER forever)
  sec/SecSource                 implements ProfileFeed, HoldingsFeed, StatementFeed, DividendFeed,
                                PeerFeed, InstitutionalFeed, InsiderFeed, FilingFeed
  alpaca/AlpacaSource           implements PriceFeed, DividendFeed
  finnhub/FinnhubSource         implements ProfileFeed, StatementFeed, PeerFeed, InsiderFeed,
                                FilingFeed, RecommendationFeed, EarningsFeed
  tiingo/, yahoo/, treasury/, bls/, bea/, eia/, worldbank/, oecd/, imf/, comtrade/,
  french/, shiller/, nber/, nyfed/, fred/, issuer/, alphavantage/
  shared/ UsGaapConcepts, SectorTaxonomy, IdentifierResolver, SeriesCatalog
```

Layer order is configuration, not code: `finrisk.data.waterfall.prices=alpaca,tiingo,yahoo`. Defaults are generated from `waterfall.py`, so re-scoring a source changes the order without touching Java.

This generalises what exists now. `MarketDataSource` (one interface with every method defaulting to empty) becomes per-resource `*Feed` interfaces, and `FailoverMarketData` (one global order) becomes `WaterfallMarketData` (one order per resource). Valuation and risk keep depending on `marketdata-api` only.

## 5. Changes this forces on the waterfall

| Resource | Change | Reason |
|---|---|---|
| prices | drop Stooq | split-only adjustment fails `adjClose*` |
| risk_free | drop Massive | 2-year depth, duplicates Treasury |
| fundamentals_per_share | no longer a resource | derived from `statements` |
| peers | contract becomes by symbol | neither source lists by sector |
| us_macro | add NY Fed first for fed funds | missing from BLS and BEA |
| recession | NBER first, FRED second; drop French/Shiller | they have no recession flag |
| trade_flows | drop World Bank | no partner country |
| insiders | drop Yahoo | no transaction code |
| earnings_calendar | contract becomes `nextEarnings(symbol)` | asked per holding |
| news_sentiment | remove the resource (recommended) | single D-grade source |
