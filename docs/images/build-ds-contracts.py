# DS-03: interface design for the waterfall, flat UML class diagram. Facts come from docs/data-sources/contracts.md,
# sections 3 and 4. Status: designed. The built code (branch refactor/java-monolith) has MarketData, FailoverMarketData
# and CachingMarketData only.
import blueprint as bp
bp.H = 1180
from blueprint import ACC, INK
import uml
from uml import klass, line, note, package, text

o = uml.sheet('Ports, feeds and the waterfall')

# --- marketdata-api: what the domain sees -------------------------------------------------
o.append(package(50, 160, 440, 770, 'MARKETDATA-API  (PURE JAVA, NO VENDORS)'))
API = [('PriceData', ['daily(symbol, from, to)', 'riskFree(tenor, from, to)']),
       ('ReferenceData', ['profile(symbol)', 'peers(symbol, limit)', 'holdings(etf)']),
       ('FundamentalsData', ['statements(symbol, period, years)', 'dividends(symbol, from, to)']),
       ('MacroData', ['series(id, from, to)', 'country(indicator, iso3, ...)', 'factors(model, from, to)',
                      'recessions()', 'trade(reporter, partner, hs, year)']),
       ('SignalsData', ['institutional(symbol)', 'insiders(symbol, since)', 'filings(symbol, forms, limit)',
                        'recommendations(symbol)', 'nextEarnings(symbol)'])]
y, api_mid = 196, []
for name, ops in API:
    svg, (x, yy, w, h) = klass(70, y, 300, name, 'interface', ops=ops, lh=17)
    o.append(svg); api_mid.append(yy + h / 2); y += h + 14
o.append(line(f'M370 {api_mid[0]} H420 V{api_mid[-1]} H370'))
for m in api_mid[1:-1]:
    o.append(line(f'M370 {m} H420'))
o.append(text(70, 900, '+ canonical records: PricePoint, CompanyProfile,', style='font-size:12px'))
o.append(text(70, 917, '   FundHoldings, FinancialStatement, ...', style='font-size:12px'))

# --- marketdata: adapters ---------------------------------------------------------------
o.append(package(530, 160, 1020, 770, 'MARKETDATA  (ADAPTERS, THE DOMAIN NEVER IMPORTS THIS)'))
svg, cm = klass(570, 196, 380, 'CachingMarketData', ops=['per-resource TTL in Caffeine', 'prices daily, 13F quarterly'], lh=17)
o.append(svg)
svg, wm = klass(570, 330, 380, 'WaterfallMarketData', ops=['implements all five *Data ports', 'one Waterfall per resource'], accent=True, lh=17)
o.append(svg)
svg, wf = klass(570, 480, 380, 'Waterfall<F extends Source>'.replace('<', '&lt;').replace('>', '&gt;'),
                ops=['first(call): Optional&lt;T&gt;', 'firstList(call): List&lt;T&gt;', 'skips unavailable layers',
                     'logs each fall-through, never throws'], accent=True, lh=17)
o.append(svg)
svg, fd = klass(570, 700, 380, 'PriceFeed, ProfileFeed, ...', 'interface',
                ops=['one feed per resource', 'empty = no data', 'throws SourceUnavailableException', '  = broken now'], lh=17)
o.append(svg)
svg, sr = klass(1030, 196, 230, 'Source', 'interface', ops=['name()', 'available()'], lh=17)
o.append(svg)
# implements the ports (dashed, hollow triangle) from Waterfall and Caching to the api bracket
o.append(line(f'M570 {cm[1]+40} H510 V{api_mid[2]} H424', 'dashed', end='tri'))
o.append(line(f'M570 {wm[1]+40} H510', 'dashed'))
o.append(text(426, api_mid[2] - 12, 'implements', style='font-size:10.5px'))
# caching wraps waterfall (uses), waterfall owns one Waterfall per resource, waterfall calls feeds
o.append(line(f'M760 {cm[1]+cm[3]} V{wm[1]-2}', 'dashed', end='open'))
o.append(text(770, cm[1] + cm[3] + 22, 'wraps', style='font-size:11px'))
o.append(line(f'M760 {wm[1]+wm[3]} V{wf[1]-2}', start='dia'))
o.append(text(770, wm[1] + wm[3] + 22, '1 per resource', style='font-size:11px'))
o.append(line(f'M760 {wf[1]+wf[3]} V{fd[1]-2}', 'dashed', end='open'))
o.append(text(770, wf[1] + wf[3] + 22, 'tries in order', style='font-size:11px'))
# feeds extend Source
o.append(line(f'M950 {fd[1]+20} H1145 V{sr[1]+sr[3]+2}', end='tri'))
o.append(text(1000, fd[1] + 12, 'extends', style='font-size:11px'))

# sources (right column)
SRC = [('SecSource', ['Profile, Holdings, Statement,', 'Dividend, Peer, Institutional,', 'Insider, Filing']),
       ('AlpacaSource', ['Price, Dividend']),
       ('FinnhubSource', ['Profile, Statement, Peer, Insider,', 'Filing, Recommendation, Earnings'])]
y = 330
for name, feeds in SRC:
    svg, (x, yy, w, h) = klass(1290, y, 250, name, attrs=feeds, lh=17)
    o.append(svg)
    o.append(line(f'M1290 {yy + 22} H1280', end=None))
    y += h + 16
src_bottom = y
o.append(line(f'M1280 352 V{src_bottom - 30} ', 'dashed'))
o.append(line(f'M1280 {src_bottom - 30} V{fd[1]+50} H952', 'dashed', end='tri'))
o.append(text(1110, fd[1] + 44, 'implements feeds', style='font-size:11px'))
o.append(text(1290, src_bottom + 14, '+ tiingo, yahoo, treasury, bls, bea, eia,', style='font-size:11.5px'))
o.append(text(1290, src_bottom + 31, 'worldbank, oecd, imf, comtrade, french,', style='font-size:11.5px'))
o.append(text(1290, src_bottom + 48, 'shiller, nber, nyfed, fred, alphavantage', style='font-size:11.5px'))

# shared adapters
svg, sh = klass(1030, 780, 500, 'shared adapters: overlap handled once', ops=[
    'UsGaapConcepts       us-gaap aliases (SEC, Finnhub)',
    'SectorTaxonomy       SIC, Finnhub, Yahoo to 11 sectors',
    'IdentifierResolver   ticker, CUSIP, CIK (OpenFIGI)',
    'SeriesCatalog        macro ID to each source code'], lh=17)
o.append(svg.replace('font-size:11px;fill:#0a0b1f', 'font-size:10.5px;fill:#0a0b1f;white-space:pre'))
o.append(line(f'M1415 {src_bottom + 56} V{sh[1]-2}', 'dashed', end='open'))
o.append(text(1425, src_bottom + 76 if src_bottom + 76 < sh[1] - 4 else sh[1] - 6, 'use', style='font-size:11px'))

# --- strip ---------------------------------------------------------------------------
o.append(note(60, 996, 640, ['Five *Data ports, one *Feed per resource, Waterfall&lt;F&gt; per resource,',
                             'WaterfallMarketData. Layer order is configuration,',
                             'for example finrisk.data.waterfall.prices.'], accent=True))
uml.finish(o, 'ds-contracts', 'DS-03 CONTRACTS', view='UML')
