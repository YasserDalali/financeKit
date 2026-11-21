# DS-04: what we store, how long it stays valid, and what we may keep. Top (3D): the read order with a stale fallback.
# Bottom (flat): storage classes, freshness per resource, rights tiers. Facts come from docs/data-sources/caching.md 1-4.
# Status: designed. Today only the Caffeine layer exists (CachingMarketData).
import blueprint as bp
bp.H = 1420
bp.VIEW, bp.TILE_H = (14, 46), 26
from blueprint import ACC, INK, badge, card, face, key, platform, tile, wire
import uml
from uml import note, text

o = uml.sheet('What we store, and for how long')
PW, PD = 1100, 290
bp.fit(PW, PD, (440, 165, 1545, 540), h=26)
o.append(platform(0, PW, PD))
H = bp.TILE_H
tiles = [
    (0, 50, 160, 150, card('app-window', 'REQUEST', 'valuation, risk'), False),
    (240, 50, 180, 150, card('cpu', 'CAFFEINE', 'in memory', lines=['hot answers,', 'minutes']), False),
    (500, 30, 230, 190, card('database', 'POSTGRES', 'store of record', ACC, lines=['schema marketdata', 'source, fetched_at', 'on every row']), True),
    (820, 50, 220, 150, card('network', 'WATERFALL', 'live layers 1..N', lines=['first complete', 'answer wins']), False),
]
for x, y, w, d, inner, acc in sorted(tiles, key=lambda t: bp.depth(t[0], t[1])):
    o.append(tile(x, y, w, d, 0, inner, acc))
o.append(face(H) +
         wire('M160 100 H238') + wire('M420 100 H498') + wire('M730 100 H818') +
         wire('M820 160 H732') +
         wire('M560 220 V262 H80 V202', 'stroke-dasharray:6 4;stroke:#0014dc') +
         badge(1, 199, 100) + badge(2, 459, 100) + badge(3, 774, 100) + badge(4, 776, 160) + badge(5, 320, 262) + '</g>')

o.append(text(60, 180, 'READ ORDER', 't'))
for i, s in enumerate(['Caffeine holds the hot answer.', 'Postgres serves inside the fresh TTL.',
                       'Past the TTL, the waterfall runs.', 'The first complete answer is stored.',
                       'All layers fail: the stored value', 'is served up to max stale,', 'with a warning.']):
    n = [1, 2, 3, 4, 5, None, None][i]
    if n:
        o.append(text(60, 206 + i * 22, f'{n}', style=f'font-size:12.5px;font-weight:700;fill:{ACC}'))
    o.append(text(82, 206 + i * 22, s, style='font-size:12.5px'))
o.append(note(60, 380, 330, ['Every response carries', 'Freshness(asOf, source, stale).', 'Nothing usable: the domain skips', 'the metric and says so.']))

# --- storage classes ----------------------------------------------------------------
y = 590
o.append(text(60, y, 'FOUR STORAGE CLASSES', 't'))
rows = [['Immutable history', 'Rows never change once written', 'delta fetch after the last stored key',
         'raw close, dividends, splits, Form 4, filings, 13F'],
        ['Revisable history', 'New rows, plus a known revised window', 'delta fetch + refetch the window',
         'GDP, payrolls, adjusted CPI, trade flows, factors'],
        ['Snapshot', 'One current value that can change', 'refetch after the TTL, keep dated versions',
         'profile, peers, issuer holdings, next earnings'],
        ['Live only', 'The terms forbid storing it', 'fetch per request, never persist', 'anything served by FRED']]
svg, h = uml.grid(60, y + 14, [200, 330, 360, 590], ['CLASS', 'MEANING', 'READ PATH', 'EXAMPLES'], rows, rh=28, tint_rows=(0,))
o.append(svg)

# --- freshness ------------------------------------------------------------------------
y2 = y + 14 + h + 46
o.append(text(60, y2, 'FRESHNESS PER RESOURCE (SAMPLE)', 't'))
rows = [['prices (raw close)', 'immutable', 'until next close', 'none', '10 trading days'],
        ['dividends, splits', 'immutable', '1 day', 'none', '30 days'],
        ['sector / profile', 'snapshot', '90 days', '-', '1 year'],
        ['statements', 'immutable facts', '1 to 7 days', 'none: restatements append', '1 year'],
        ['us_macro', 'revisable', 'next release', 'GDP 3 yrs, payrolls 2 months', '3 months'],
        ['institutional (13F)', 'per quarter', 'next filing window', '13F-A in the quarter', '1 quarter'],
        ['ratings', 'monthly', '7 days', 'current month', '3 months'],
        ['earnings_calendar', 'snapshot', '1 day, 6 h last week', '-', 'until the date']]
svg, h2 = uml.grid(60, y2 + 14, [170, 130, 170, 230, 130], ['RESOURCE', 'CLASS', 'FRESH TTL', 'REVISION WINDOW', 'MAX STALE'],
                   rows, rh=26, size=12, mono_cols=(0,))
o.append(svg)
xr = 990
o.append(text(xr, y2, 'THE RAW-CLOSE TRICK', 't'))
o.append(note(xr, y2 + 14, 550, ['An adjusted close changes after each later dividend or split.',
                                 'A raw close never changes. So we store the raw close plus',
                                 'the corporate actions, and compute adjClose on read.',
                                 'Past price rows never need a rewrite.',
                                 '',
                                 'A delta from a different layer refetches the last stored day.',
                                 'If the closes differ by more than 0.5 %, the full window',
                                 'reloads from the new layer. Layers are never mixed.'], accent=True))

# --- rights ---------------------------------------------------------------------------
y3 = y2 + 14 + h2 + 46
o.append(text(60, y3, 'WHAT WE MAY STORE AND SHOW', 't'))
rows = [['Store and show freely', 'SEC EDGAR, US Treasury, BLS, BEA, EIA, NY Fed, NBER, OpenFIGI', 'SEC: declared User-Agent, 10 req/s'],
        ['Store and show, cite', 'World Bank (CC BY 4.0), OECD, IMF, Kenneth French, Shiller', 'cite the source where shown'],
        ['Store, personal use only', 'Alpaca, Tiingo, Finnhub, Yahoo, Alpha Vantage, UN Comtrade', 'keep behind a login'],
        ['Terms unknown', 'issuer holdings CSVs (iShares, SPDR, Vanguard)', 'do not scrape yet'],
        ['Do not store', 'FRED', 'live only, no stale fallback']]
svg, h3 = uml.grid(60, y3 + 14, [220, 560, 320], ['RIGHTS', 'SOURCES', 'CONSTRAINT'], rows, rh=27, tint_rows=(0,))
o.append(svg)
o.append(text(1200, y3, 'ONE DATABASE, NO REDIS', 't'))
for i, s in enumerate(['History is the asset. It must', 'survive restarts and redeploys.',
                       'Delta fetch asks for the last date', 'held: one indexed query.',
                       'Peers and look-through are joins.', 'Caffeine keeps hot reads in memory,',
                       'so most reads skip the database.']):
    o.append(text(1200, y3 + 26 + i * 21, s, style='font-size:12.5px;fill:#0a0b1f'))
uml.finish(o, 'ds-caching', 'DS-04 CACHING', view='AXO 14/46')
