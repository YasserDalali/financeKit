# Free financial data source inventory (personal, non-commercial, heavy caching)

Researched 2026-11-21. Tags: **[V]** read on the provider's own page this session; **[S]** secondary/third-party source only; **[K]** prior knowledge, not re-verified; **[?]** could not be verified. Provider terms change often, so re-check before building on any row. Nothing here is legal advice.

Context: heavy local caching, low daily quota OK, so what matters is history depth, dataset coverage, and whether the ToS allows storing the data.

## 0. Graded supply table (LP view)

Read it as a linear program. Each source *s* is a variable *x_s* (use it or not). Its **cost** is the price on the free tier. Its **constraints** cap how much we can pull from it. Its **supply** is the demand rows it can fill. Demand: every dataset kept in scope needs one primary and one fallback. Objective: cover all demand at $0 while minimising calls and breakage risk. Heavy caching means one full pull of history, then small daily deltas, so depth and storage terms matter more than per-day quotas.

Grade rubric: **A** official, free, deep, cacheable. **B** solid with one binding constraint. **C** usable with a serious constraint (tiny quota, unofficial, or a no-cache clause). **D** marginal for this project. **F** not usable.

Demand codes: P prices, S sector/type, E ETF holdings, R risk-free, F statements, Q ratios, V FCF/EPS/shares, D dividends, N peers, M macro, X recession flag, C commodities, T trade flows, I institutional holders, K insiders, G filings, A analyst ratings, Y earnings calendar, W news sentiment. Upper case = full supply, lower case = partial.

| Source | Grade | Cost (free tier) | Rate constraint | Volume constraint | History depth | Storage / terms | Supply |
|---|---|---|---|---|---|---|---|
| SEC EDGAR (APIs + bulk sets) | **A** | $0, no key | 10 req/s, UA with contact | none; nightly bulk zips | statements 2009+, Form 4 2006+, 13F 2013+, N-PORT 2019Q4+ | public domain | F V D(dps tag, patchy) N(via SIC) I K G E(N-PORT, quarterly) S |
| US Treasury (FiscalData + yield curve) | **A** | $0, no key | none stated | none | decades | free, no restriction | R M(rates) |
| OpenFIGI | **A** | $0, optional key | 25/min (250/min with key) | 10 (100) jobs per req | n/a | free | identifier map (CUSIP to ticker for I, E) |
| Tiingo | **A-** | $0, key | 50/hr | 1,000/day, 500 symbols/month, 1 GB/month | decades (free depth unverified) | personal use | P D |
| EIA Open Data | **B+** | $0, key | not stated | not stated | decades | free | C(energy) |
| Alpaca | **B+** | $0, paper account | 200/min | none | 7+ yrs | personal, no redistribution | P D(corporate actions) |
| Finnhub | **B+** | $0, key | 60/min | none | varies (news 1 yr) | personal use | A K G N Q s(profile) y(1-month window) |
| BLS / BEA | **B** | $0, key | BLS 500 queries/day | 20 yrs per call | decades | public | M (CPI, jobs, GDP) |
| UN Comtrade | **B** | $0, key | 100–500 calls/day (conflicting) | 100k records/call | 1962+ | non-commercial | T |
| World Bank | **B** | $0, no key | not stated | none | decades, annual | CC BY 4.0 | M(global, annual) |
| Kenneth French / Shiller | **B** | $0 static files | n/a | n/a | 1926+ / 1871+ | academic, attribute | M(factors, long history) x |
| Issuer holdings CSVs (iShares, SPDR, Vanguard) | **B-** | $0 | none | one file per fund | current only | terms unknown, unofficial URLs | E (that issuer's funds, daily) |
| Yahoo / yfinance | **C+** | $0, no key | unpublished, 429s | none | prices decades, statements 4–5 yrs | personal use, unofficial | P S F(short) D I(top) K A Y e(top 10) |
| FRED | **C** | $0, key | 120/min | none | decades | **no storing or caching** | M X C |
| Alpha Vantage | **C** | $0, key | not stated | **25/day** | daily compact only; weekly adjusted long | not read | f v e(ETF_PROFILE) m c Y |
| OECD | **C** | $0, no key | 20–60/hr (conflicting) | none | decades | not read | M(global) |
| Stooq | **C** | $0, CAPTCHA key (new) | unpublished daily cap | none | decades | none found, unofficial | p(split- but not dividend-adjusted) |
| IMF | **C-** | $0, maybe account | not stated | not stated | decades | not read; API in migration | M(global) c(PCPS) t(DOTS) |
| GDELT | **D** | $0, no key | informal | huge raw files | 2013+ | free, attribute | w(tone only) |
| Massive (ex-Polygon) | **D** | $0, key | 5/min | none | **2 yrs** | not read | p d s R |
| FMP | **D?** | $0, key | not stated | 250/day | unverified | not read | unverified (p s, rest paid?) |
| SimFin | **D** | $0, key | 2/s | 500 credits/month | 5–7 yrs, delayed | **delete on expiry** | f |
| Twelve Data | **D** | $0, key | 8/min | 800/day | unverified | not read | p |
| Nasdaq Data Link | **D** | $0, key | unverified | unverified | varies | varies | m c (small free catalog) |
| EODHD | **F** | $0, key | 20/min | 20/day | 1 yr | not read | p d |
| Marketstack | **F** | $0, key | n/a | 100/month | 1 yr | non-commercial | p |
| Intrinio | **F** | $150/month, no free tier | — | — | — | — | — |
| IEX Cloud | **F** | shut down 2024-08-31 | — | — | — | — | — |

Binding constraints after caching: Tiingo's 500 symbols/month caps the price universe; Alpha Vantage's 25/day makes it a slow backfill only; FRED's no-cache clause rules it out as a stored source; N-PORT's 60-day lag bounds ETF freshness.

## 1. Per-source table

| Source | Free limits | Free-tier datasets (precise) | Key | Personal / non-commercial terms | Stability | Gotchas |
|---|---|---|---|---|---|---|
| **Massive** (ex-Polygon.io) | Stocks Basic: 5 req/min per asset class, no daily cap [V]; EOD only; **2 yrs history** [V] | Daily/custom bars, split-adjusted by default [V]; dividends and ticker overview (SIC, market cap, shares) on Basic, 2 yr limit [V]. Treasury yields "all plans" [V, Basic not named]. **No** financial statements (needs Financials & Ratios $29/mo or Advanced) [V]. **No** flat files on Basic [V]. ETF holdings only via paid ETF Global partner dataset ($99/mo) [V] | Yes (free signup) | [?] terms not read | Official API | Rebrand confirmed: Polygon.io became Massive, effective 2025-10-30; api.massive.com live, api.polygon.io still works but "phased out in the new year" [V]. A day's bars appear only after midnight ET, earlier requests return 403 [S via Massive KB]. 2-year depth is too short for risk work |
| **FMP** free (Basic) | 250 calls/day, 500 MB per trailing 30 days [S, partly FMP help pages] | End-of-day only; "US only" per third-party comparison [S]; history depth on free **unverified** (one source says ~5 yrs) [?]. Statements, ratios, profile, peers, price-target and estimates availability on free **unverified** [?]. ETF holdings and 13F reported as higher-tier [S] | Yes | [?] not read (pricing pages returned 403) | Official API | FMP pricing pages blocked automated fetch. Many endpoints are symbol-restricted or paid on free; test with a real key before relying on it |
| **Yahoo / yfinance** | No published limits; community reports 429s [S] | Adjusted daily history (decades), statements (quarterly about 4, annual about 4-5 yrs [K]), holders, insider, analyst targets/recs, ETF top-10 holdings only [K], earnings dates, calendar | No | Yahoo's API terms bar earning income from it; yfinance docs say personal use [S] | **Unofficial scraping**, breaks without notice (e.g. Feb 2025 redesign) [S] | Best breadth, worst reliability. Use as a fallback, cache aggressively, wrap in try/retry. ETF "full" holdings not available |
| **Alpha Vantage** | **25 req/day**; per-minute not stated on free [V] | `TIME_SERIES_DAILY` compact only (about 100 pts); `outputsize=full` is premium [V]. `DAILY_ADJUSTED` premium [V]. Weekly/monthly (adjusted) not flagged premium [V]. Income/balance/cash flow, ETF_PROFILE (holdings), SHARES_OUTSTANDING, earnings history and estimates, earnings and IPO calendar: no premium flag seen [V, annual+quarterly, depth not stated]. Macro (CPI, GDP, fed funds, unemployment, treasury yield) and commodities (WTI, Brent, copper, gold/silver): no premium flag seen [V]. Insider, institutional, news sentiment: **not checked** [?] | Yes | [?] | Official API | 25/day is very tight but fundamentals and ETF_PROFILE are usable for slow cache fills. Weekly-adjusted gives long adjusted history in one call [K] |
| **Finnhub** | 60 calls/min [S] | **Free:** `profile2`, `stock/metric` (ratios), `financials-reported` (as-reported SEC), `recommendation` trends, `insider-transactions`, `insider-sentiment`, `filings`, `peers`, `symbol`, company news (1 yr), earnings calendar (1 month window) [V swagger flags]. **Premium:** `stock/candle` (price history), `financials` (standardized), `price-target`, `upgrade-downgrade`, `eps-estimate`, `revenue-estimate`, `etf/holdings`, `etf/profile`, `dividend`/`dividend2`, `split`, `ownership`, `fund-ownership`, `institutional/*`, `news-sentiment`, historical market cap [V swagger flags]. `supply-chain` and `/economic` **not seen** [?] | Yes | Free tier is personal use [S]; [?] | Official API | Candles became premium (do not use for prices). Strong free source for analyst recommendation trends and insider transactions |
| **Tiingo** | 50 req/hr, 1,000/day, 500 unique symbols/month, 1 GB/month [V] | EOD daily OHLCV, split/dividend adjusted, decades back (to 1962 per third-party) [S]; free-tier depth not confirmed [?]. Fundamentals: only DOW 30, 3 yrs, "evaluation" [V]. News: 3 months history [V] | Yes | "Internal use only", personal use [V] | Official API | Best clean adjusted price history on free; 500 symbols/month is the real cap. Free fundamentals not useful |
| **Twelve Data** Basic | 8 credits/min, 800/day [V] | Market data and technical indicators, ETF market data [V]. **No** fundamentals (statements, stats) [V], no ETF reference/holdings [V]. `time_series` is 1 credit [V]; depth on free not stated [?] | Yes | [?] | Official API | Prices only on free; US coverage on free not confirmed [?] |
| **EODHD** Free | **20 calls/day** (plus one-time 500 bonus), 20/min [V] | **1 year** EOD history only; dividends/splits, news and sentiment, US Treasury yields, commodities [V]. **No** fundamentals, intraday, economic data, insider, filings, calendar [V] | Yes | [?] | Official API | Free tier was cut hard: 1 yr depth. Not useful beyond demo |
| **Marketstack** Free | 100 req/month, 1 yr history, HTTPS [V] | EOD prices only | Yes | **Non-commercial only** [V] | Official API | Useless for this project |
| **Stooq** | No published limits; daily-hits cap exists ("Exceeded the daily hits limit") [S] | Daily OHLC history, long depth, global (US, indices, FX, some commodities); `https://stooq.com/q/d/l/?s=spy.us&i=d` CSV [S]. Bulk `stooq.com/db/h/` [?, page empty to fetcher] | **Now a CAPTCHA-derived apikey** reported (2026-03) [S] | [?] no official terms found | Unofficial, undocumented | Break risk: key requirement is new and undocumented. Prices are split-adjusted, not dividend-adjusted [K]. Good no-account fallback for indices and long history |
| **Nasdaq Data Link** | [?] limits page 404/redirect | Free datasets are now a small curated set (e.g. FRED mirror, some CFTC/commodity series); WIKI prices discontinued [K]; Sharadar/Zacks/etc. paid [K] | Yes | [?] | Official | Not a primary source; check the free catalog before use [?] |
| **SimFin** Free | 2 calls/sec; 500 monthly credits; 8 filing downloads/day [V] | About 5,000 US stocks. Fundamentals **7 yrs via API, 5 yrs via bulk CSV** (page is inconsistent) and bulk is delayed [V]. Daily prices listed in plan table, details unclear [V/?]. **Ratios, derived metrics, as-reported not in free bulk** [V] | Yes | Data usable only while you hold a valid subscription; **delete when it ends** [V] | Official | Licence conflicts with "cache forever". Delayed bulk. OK as a cross-check, not a foundation |
| **SEC EDGAR** | 10 req/sec, must send a declared User-Agent with contact email [V] | `companyfacts` (all XBRL facts, one call), `companyconcept`, `frames`, `submissions` [V]; nightly bulk `companyfacts.zip` and `submission.zip` rebuilt about 03:00 ET [V]. Statement-level history back to about 2009 (XBRL era) [K] | No | US government, public [K]; fair-access policy applies [V] | Official | Raw XBRL needs tag mapping (revenue has several tags, quarterly Q4 must be derived). Companies are keyed by CIK; no price data. Best free statement source for US filers |
| **SEC Form 4 / insider data sets** | Bulk ZIP download | Forms 3/4/5 quarterly flattened sets, **2006-01 to 2026-09** [V]; updated quarterly [V] | No | Public | Official | As-filed, accuracy not guaranteed [V]. Per-filing XML via `submissions` for fresher data [K] |
| **SEC 13F data sets** | Bulk ZIP | Quarterly flattened sets **2013 Q2 to 2026-Aug** [V]; since March 2024 they cover 3-month windows ending Feb/May/Aug/Nov [V] | No | Public | Official | Holdings keyed by CUSIP, not ticker (needs OpenFIGI). 45-day filing lag; 13F covers long US equity positions only [K] |
| **SEC N-PORT data sets** | Bulk ZIP (about 441 MB per quarter) | **2019 Q4 to 2026 Q3** [V]; registered funds and ETFs (UIT ETFs included), excludes money market funds [V]. Monthly holdings filed; public ones are quarter-end months only, about 60-day lag [K] | No | Public | Official | **Only free source of FULL ETF holdings.** Series IDs map to tickers via SEC's separate fund/ticker file [K]. Large files, quarterly lag |
| **FRED** | 120 req/min [K] | 800k+ macro series: rates, CPI, GDP, unemployment, recession indicator `USREC`, T-bill/treasury, commodities (WTI `DCOILWTICO`), many with full history; vintage data via ALFRED [K] | Yes (free) | **API terms prohibit storing, caching or archiving FRED content** and sharing it; commercial use needs consent; some series third-party copyrighted [V] | Official | **Conflicts with the caching design.** Mitigation: fetch live with short TTL, or source the same series from the underlying agency (BLS, BEA, Treasury, EIA, Fed). Needs your own legal read |
| **World Bank** | No key needed, limits not stated [V] | Annual country indicators (GDP, inflation, trade % GDP, etc.), decades [K]; V2 only [V] | No | [?] site terms linked; data is CC BY 4.0 for most [K] | Official | Annual/slow; no market data |
| **IMF** | Beta portal; SDMX 2.1 and 3.0 APIs [V]; key/limits not stated [?] | WEO, IFS, direction of trade, commodity prices (PCPS) [K] | Beta-portal account may be required [?] | [?] | Official, **in migration** (new portal beta [V]) | Legacy `dataservices.imf.org` status unverified [?]. Expect endpoint changes |
| **OECD** | **60 downloads/hour** per OECD page [S, conflicting copy says 20/min and 20/hr]; no key | Leading indicators, CLI, unemployment, trade (TiVA), prices (SDMX) [K] | No | [?] | Official | Rate-limited; query parameter restrictions added 2026-03 [S]. TiVA had planned downtime 2026-06 [S] |
| **GDELT** | Free, no key, no stated cap [V] | Events (1.0 from 1979 reduced and 2013+; 2.0 15-minute updates), GKG (2013+), DOC/GEO/TV JSON APIs, BigQuery [V]. Tone/theme signals usable as geopolitical or news-sentiment proxies | No | "100% free and open" [V]; attribution requested [K] | Official but best-effort | Very noisy; DOC API is rate-limited informally [K]. Raw files are huge (2015 GKG alone >2.5 TB [V]) |
| **UN Comtrade** | Free key: 500 calls/day, 100k records/call [S, official wiki quoted via search]; other sources say 100 or 250 [S, conflicting]; keyless preview 500 records [S] | Annual/monthly bilateral trade by HS commodity, 1962+ (HS from 1988) [K] | Yes (free) | Free tier is non-commercial [K]; [?] | Official | Bulk files need premium [V]. Great fit for caching (annual data). Pagination plus record cap needs chunked queries |
| **Alpaca** Free | 200 historical calls/min [V] | IEX-only feed; 15-minute delay on API [V]; **7+ yrs** history [V]; stocks, options (indicative), crypto, corporate actions [V]; news [?] | Yes (free paper account) | Personal use; data redistribution forbidden [K] | Official | IEX-only means thin volume (about 2-3 % of US volume [K]), but OHLC adjusted for splits and dividends; SIP history older than 15 min on free is reported [K, unverified]. Strong primary for daily bars at high call volume |
| **Intrinio** | No free tier; trial only; Individual $150/mo [V] | n/a | Yes | Individual = personal use | Official | Not free. Skip |
| **IEX Cloud** | Shut down 2024-08-31 [S, several outlets] | n/a | n/a | n/a | **Dead** | Confirmed retired; IEX exchange itself unaffected. One report of an asset buyer; no follow-up found [S] |
| **OpenFIGI** | No key: 25 mapping req/min, 10 jobs/req. With free key: 250/min, 100 jobs/req [V] | Maps ticker, CUSIP, ISIN, SEDOL to FIGI and back; security type, exchange, name [V] | Optional | Free [V] | Official (Bloomberg) | Essential for 13F CUSIP-to-ticker. Cache mappings forever |
| **US Treasury FiscalData** | No key, no stated limits [V] | Average interest rates, exchange rates, debt, etc. [V]; Daily par yield curve is on treasury.gov (XML/CSV) [K] | No | "Free, without restriction", commercial OK [V] | Official | Use for risk-free rate (3-month bill) without FRED's caching clause |
| **EIA Open Data v2** | Free key; limits not stated [V] | Petroleum and natural gas spot/futures prices, daily to annual [V] (WTI/Brent series not named on page [?]); bulk files twice daily [V] | Yes | Free [V] | Official | Good FRED-free commodity source |
| **BLS / BEA / ECB / BIS** | [K] BLS v2: 500 queries/day with key, 20 yrs per call | CPI, unemployment, payrolls (BLS); GDP (BEA); euro-area rates and FX (ECB SDW); policy rates (BIS) | BLS/BEA key | Public data | Official | Not verified this session [?]. Use as FRED-free underlying sources |
| **Fund-issuer holdings files** (iShares, SPDR, Vanguard) | None (public CSV links) | Daily/near-daily full holdings per fund; iShares CSV at `.../latest-holdings.csv` style URL with as-of date, ticker, sector, weight [S] | No | Terms on bulk scraping not found [?] | Unofficial (URL patterns change) | Covers only that issuer's funds; fresher than N-PORT. Check terms before scraping |
| **Kenneth French / Shiller / AQR data libraries** | Static files | Factor returns, long US market series (1871+ for Shiller) [K] | No | Academic, attribution [K] | Stable files | Useful for stress-test history and benchmark factors. Not verified this session [?] |
| **Frankfurter / ECB FX** | No key [K] | Daily FX reference rates 1999+ | No | Free | Official-derived | Not verified this session [?] |

## 2. Per-lens coverage (best primary + fallback)

Legend: ✅ good free source, 🟡 partial/with caveats, ❌ no good free source.

### Lens 1: Portfolio risk
| Dataset | Status | Primary | Fallback |
|---|---|---|---|
| Daily adjusted prices (stocks, ETFs, SPY) | ✅ | Tiingo EOD (500 symbols/month, adjusted, deep history) | Alpaca free (7+ yrs, 200/min, IEX-sourced bars), Stooq (no dividend adjustment), yfinance |
| Sector / asset type | 🟡 | SEC `submissions` (SIC code) for stocks; Finnhub `profile2` (industry) | yfinance `info`; Massive ticker overview (SIC) |
| FULL ETF holdings | 🟡 | SEC N-PORT bulk (full, but quarterly, about 60-day lag) | Issuer CSVs (iShares etc., fresher, terms unclear); Alpha Vantage `ETF_PROFILE` (25/day, depth of holdings unverified) |
| Risk-free rate | ✅ | Treasury par yield curve / FiscalData | FRED `DGS3MO` (caching clause), Alpha Vantage `TREASURY_YIELD`, Massive treasury yields |

### Lens 2: Fundamentals
| Dataset | Status | Primary | Fallback |
|---|---|---|---|
| Income, balance, cash flow, multi-year | ✅ | SEC EDGAR `companyfacts` (US filers, about 2009+, as reported) | Alpha Vantage statements (25/day), Finnhub `financials-reported`, SimFin free (5-7 yrs), yfinance (about 4-5 yrs) |
| Ratios | 🟡 | Compute from EDGAR + prices | Finnhub `stock/metric` (free), SimFin (not in free bulk) |

### Lens 3: Intrinsic valuation
| Dataset | Status | Primary | Fallback |
|---|---|---|---|
| FCF, EPS | ✅ | Derived from EDGAR cash flow and income | Alpha Vantage, Finnhub as-reported |
| Shares outstanding | ✅ | EDGAR (`dei:EntityCommonStockSharesOutstanding`, weighted shares) | Alpha Vantage `SHARES_OUTSTANDING`, Massive ticker overview |
| Dividends per share | ✅ | Massive dividends (2 yrs only) / Tiingo `divCash` from EOD | Alpaca corporate actions, EDGAR `CommonStockDividendsPerShareDeclared`, yfinance |
| Sector peers list | 🟡 | Finnhub `stock/peers` (free) | Build from SIC code via EDGAR; yfinance |
| Peer multiples (P/E, P/S, EV/EBITDA) | 🟡 | Compute from EDGAR fundamentals + price + shares | Finnhub `stock/metric` (free), yfinance |

### Lens 4: Stress testing
| Dataset | Status | Primary | Fallback |
|---|---|---|---|
| Rates, CPI, GDP, unemployment | ✅ | FRED (live, caching clause) | BLS/BEA direct, Alpha Vantage macro, World Bank/IMF/OECD for global annual |
| Recession flags | ✅ | FRED `USREC` / NBER dates (NBER publishes dates) [K] | Derive from GDP/yield-curve inversion |
| Commodities | ✅ | EIA (energy), FRED, Alpha Vantage commodities | IMF PCPS (monthly), Stooq futures, EODHD (1 yr) |
| Trade flows | 🟡 | UN Comtrade (annual/monthly) | World Bank WITS/IMF DOTS, OECD TiVA |

### Lens 5: Market intelligence
| Dataset | Status | Primary | Fallback |
|---|---|---|---|
| Institutional holders per stock | 🟡 | SEC 13F bulk (+ OpenFIGI), 45-day lag | yfinance `institutional_holders`; Finnhub/FMP are premium |
| Insider transactions | ✅ | SEC Form 3/4/5 data sets + `submissions` | Finnhub `insider-transactions` (free), yfinance |
| Filings | ✅ | SEC `submissions` | Finnhub `filings` |
| Analyst ratings | ✅ | Finnhub `recommendation` trends (free) | yfinance recommendations |
| Earnings calendar | 🟡 | Alpha Vantage `EARNINGS_CALENDAR` (free per docs flags) | Finnhub (1-month window on free), yfinance |
| News sentiment | 🟡 | GDELT tone; Tiingo news (3 months) | Finnhub `news-sentiment` premium; Alpha Vantage `NEWS_SENTIMENT` not checked [?] |

## 3. Gaps

Out of scope by decision (2026-11-21): geopolitical event signals, analyst price targets and estimates, growth estimates, company supply-chain relationships.

1. **Full ETF holdings with history:** N-PORT is quarterly with lag; issuer CSVs are current only (you must snapshot daily to build history) and their scraping terms are unconfirmed.
2. **Deep adjusted price history from a clean official free API:** Massive free = 2 yrs; EODHD = 1 yr; Marketstack = 1 yr and 100 calls/month; Alpha Vantage full outputsize is premium. Tiingo or Alpaca fill this.
3. **Standardized fundamentals pre-2009 or non-US filers:** EDGAR XBRL starts about 2009; no free source for earlier or foreign issuers beyond yfinance snippets.
4. **FRED caching ban** vs. heavy caching. Prefer underlying agencies or accept short-TTL fetches.
5. **Institutional holders freshness:** 13F is 45 days late and long-only.

## 4. Could not verify

- Finnhub: `supply-chain`, `/economic`, `/stock/earnings` flags (swagger read only about 300 KB of 590 KB); pricing page was JS-only.
- FMP free plan: history depth, endpoint list, US-only claim (pricing pages 403).
- Massive: ToS terms; whether Basic includes economy endpoints other than treasury yields; ETF holdings are paid (partner).
- Alpha Vantage: insider, institutional and news-sentiment flags; per-minute limit on free; statements depth.
- Tiingo: free EOD history depth.
- Stooq: key/CAPTCHA requirement (third-party only), bulk page.
- Nasdaq Data Link: rate limits and current free catalog.
- OECD limit (60/hr vs 20/hr conflicting), IMF key requirement, Comtrade daily call figure (100/250/500 conflicting).
- Terms of use for Yahoo, Alpaca, iShares/SPDR/Vanguard, Comtrade, GDELT.
- FRED rate limit 120/min [K]; BLS/BEA/ECB/BIS, Kenneth French, Frankfurter.

## 5. URLs checked

- https://massive.com/pricing, https://massive.com/blog/polygon-is-now-massive, https://www.ny5.massive.com/blog/free-data-apis
- https://massive.com/knowledge-base/article/what-is-the-request-limit-for-massives-restful-apis
- https://massive.com/docs/rest/stocks/fundamentals/balance-sheets, .../corporate-actions/dividends, .../aggregates/custom-bars, .../tickers/ticker-overview, .../economy/treasury-yields, https://massive.com/docs/flat-files/stocks/day-aggregates
- https://multiples.vc/compare/fmp-api-alternatives (FMP via third party); FMP's own pages returned 403
- https://www.alphavantage.co/premium/, https://www.alphavantage.co/documentation/ (read about 630 KB of 819 KB)
- https://finnhub.io/static/swagger.json (partial)
- https://www.tiingo.com/about/pricing, https://www.tiingo.com/documentation/fundamentals
- https://twelvedata.com/pricing, https://eodhd.com/pricing, https://marketstack.com/pricing
- https://www.simfin.com/en/prices/
- https://www.sec.gov/search-filings/edgar-application-programming-interfaces, https://www.sec.gov/about/webmaster-frequently-asked-questions
- https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets, .../insider-transactions-data-sets, .../form-n-port-data-sets
- https://fred.stlouisfed.org/legal/, https://fred.stlouisfed.org/docs/api/fred/v2/index.html
- https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation
- https://data.imf.org/en/Resource-Pages/IMF-API
- https://www.oecd.org/en/data/insights/data-explainers/2024/11/Api-best-practices-and-recommendations.html (via search)
- https://www.gdeltproject.org/data.html
- https://comtradeplus.un.org/ and https://comtradewiki.azurewebsites.net (via search)
- https://alpaca.markets/data, https://docs.alpaca.markets/docs/about-market-data-api
- https://www.openfigi.com/api/documentation
- https://www.intrinio.com/pricing
- https://fiscaldata.treasury.gov/api-documentation/, https://www.eia.gov/opendata/
- IEX Cloud shutdown: https://www.alphavantage.co/iexcloud_shutdown_analysis_and_migration/, https://www.waterstechnology.com/node/7951882 (via search)
- yfinance / Yahoo terms and Stooq key: secondary search results only
