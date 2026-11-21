"""Compute the source waterfall for every data resource FinRisk needs.

Model (optimal sequential search, Smith's rule): a waterfall tries sources in
order until one answers. Each attempt at source i succeeds with probability p_i
and costs c_i. The order that minimises expected cost until success is
descending p_i / c_i. So:

  p = reliability(grade) * coverage      coverage: full 1.0, partial 0.5
  c = 1 + quota_pressure + cache_penalty
  score = p / c, highest first

Run: python3 docs/data-sources/waterfall.py > docs/data-sources/waterfall.md
"""

RELIABILITY = {"A": .99, "A-": .97, "B+": .95, "B": .92, "B-": .85, "C+": .75,
               "C": .70, "C-": .60, "D": .50, "D?": .40, "F": .20}

# source: (grade, quota_pressure, cache_penalty)
# quota_pressure: 0 unlimited/high, .5 ~1k/day, 1 <=500/day or 5/min, 2-4 tiny
# cache_penalty: 2 when the terms forbid storing (every read goes live)
SOURCES = {
    "SEC EDGAR": ("A", 0, 0), "NBER": ("A", 0, 0), "NY Fed": ("A", 0, 0), "US Treasury": ("A", 0, 0), "Tiingo": ("A-", .75, 0),
    "EIA": ("B+", .25, 0), "Alpaca": ("B+", 0, 0), "Finnhub": ("B+", 0, 0),
    "BLS / BEA": ("B", .5, 0), "UN Comtrade": ("B", 1, 0), "World Bank": ("B", 0, 0),
    "French / Shiller": ("B", 0, 0), "Issuer CSVs": ("B-", 0, 0), "Yahoo": ("C+", .5, 0),
    "FRED": ("C", 0, 2), "Alpha Vantage": ("C", 3, 0), "OECD": ("C", 1, 0),
    "Stooq": ("C", .5, 0), "IMF": ("C-", .25, 0), "GDELT": ("D", .5, 0),
    "Massive": ("D", 1, 0), "FMP": ("D?", 1, 0), "SimFin": ("D", 2, 0),
    "Twelve Data": ("D", .5, 0), "EODHD": ("F", 3, 0), "Marketstack": ("F", 4, 0),
}

F, G, P = 1.0, 0.75, 0.5  # full, full-but-degraded, partial
SUPPLY = {
    "SEC EDGAR": {"sector": F, "etf_holdings": F, "statements": F, "ratios": F,
                  "dividends": P, "peers": P, "institutional": F, "insiders": F, "filings": F},
    "US Treasury": {"risk_free": F, "us_macro": P},
    "Tiingo": {"prices": F, "dividends": F},
    "EIA": {"commodities": F},
    "Alpaca": {"prices": G, "dividends": F},  # free feed is IEX-only: thin volume,
    "Finnhub": {"ratings": F, "insiders": F, "filings": F, "peers": F, "ratios": F, "sector": F,
                "earnings_calendar": P, "statements": P},
    "BLS / BEA": {"us_macro": F},
    "UN Comtrade": {"trade_flows": F},
    "World Bank": {"global_macro": F},  # no partner country, so no trade_flows
    "French / Shiller": {"factor_history": F},
    "NBER": {"recession": F},
    "NY Fed": {"us_macro": P},  # fed funds (EFFR) only
    "Issuer CSVs": {"etf_holdings": P},
    "Yahoo": {"prices": F, "sector": F, "statements": P, "dividends": F, "institutional": P,
              "ratings": F, "earnings_calendar": F, "etf_holdings": P},
    "FRED": {"us_macro": F, "recession": F, "commodities": F, "risk_free": F},
    "Alpha Vantage": {"statements": P, "etf_holdings": P, "us_macro": P,
                      "commodities": P, "earnings_calendar": F},
    "OECD": {"global_macro": F, "us_macro": P},
    "Stooq": {},  # split-only adjustment fails adjClose*
    "IMF": {"global_macro": P, "commodities": P, "trade_flows": P},
    "GDELT": {},  # news_sentiment removed
    "Massive": {"prices": P, "dividends": P, "sector": P},
    "FMP": {"prices": P, "sector": P},
    "SimFin": {"statements": P},
    "Twelve Data": {"prices": P},
    "EODHD": {"prices": P, "dividends": P},
    "Marketstack": {"prices": P},
}

# lens -> [(resource, port method -> canonical type)]
CONTRACTS = {
    "Risk": [("prices", "PriceSource.daily(symbol, from, to) -> List<PricePoint>"),
             ("sector", "ReferenceSource.profile(symbol) -> CompanyProfile"),
             ("etf_holdings", "FundSource.holdings(etf, asOf) -> List<EtfHolding>"),
             ("risk_free", "PriceData.riskFree(tenor, from, to) -> List<RatePoint>")],
    "Fundamentals": [("statements", "FundamentalsSource.statements(symbol, period, years) -> List<FinancialStatement>"),
                     ("ratios", "FundamentalsSource.ratios(symbol) -> Ratios  (computed in-house when missing)")],
    "Valuation": [
                  ("dividends", "CorporateActionSource.dividends(symbol, from, to) -> List<Dividend>"),
                  ("peers", "ReferenceData.peers(symbol, limit) -> List<Peer>")],
    "Stress": [("us_macro", "MacroSource.series(seriesId, from, to) -> MacroSeries  (CPI, jobs, GDP, rates)"),
               ("global_macro", "MacroSource.country(indicator, country, from, to) -> MacroSeries"),
               ("factor_history", "MacroSource.factors(model, from, to) -> List<FactorReturn>  (long stress history)"),
               ("recession", "MacroSource.recessions() -> List<DateRange>"),
               ("commodities", "MacroSource.commodity(code, from, to) -> MacroSeries"),
               ("trade_flows", "TradeSource.flows(reporter, partner, hsCode, year) -> List<TradeFlow>")],
    "Market intel": [("institutional", "OwnershipSource.institutional(symbol, quarter) -> List<Holder>"),
                     ("insiders", "OwnershipSource.insiders(symbol, since) -> List<InsiderTrade>"),
                     ("filings", "FilingSource.list(symbol, forms, limit) -> List<Filing>"),
                     ("ratings", "AnalystSource.recommendations(symbol) -> List<RecommendationTrend>"),
                     ("earnings_calendar", "SignalsData.nextEarnings(symbol) -> Optional<EarningsEvent>")],
}


def score(source, resource):
    grade, quota, cache = SOURCES[source]
    p = RELIABILITY[grade] * SUPPLY[source][resource]
    return p / (1 + quota + cache)


def waterfall(resource, depth=4):
    ranked = sorted((s for s in SUPPLY if resource in SUPPLY[s]), key=lambda s: -score(s, resource))
    return ranked[:depth]


def main():
    print("# Source waterfalls\n\nGenerated by `waterfall.py`. Order = descending p/c (see the script docstring).\n")
    for lens, rows in CONTRACTS.items():
        print(f"## {lens}\n\n| Resource | Contract | 1st | 2nd | 3rd | 4th |\n|---|---|---|---|---|---|")
        for resource, contract in rows:
            cells = [f"{s} ({score(s, resource):.2f})" for s in waterfall(resource)]
            cells += ["—"] * (4 - len(cells))
            print(f"| {resource} | `{contract}` | " + " | ".join(cells) + " |")
        print()


if __name__ == "__main__":
    assert all(r in SUPPLY[s] for s in SUPPLY for r in SUPPLY[s])
    assert all(waterfall(r) for rows in CONTRACTS.values() for r, _ in rows), "a resource has no source"
    assert waterfall("prices")[0] != "Marketstack" and score("FRED", "us_macro") < score("BLS / BEA", "us_macro")
    main()
