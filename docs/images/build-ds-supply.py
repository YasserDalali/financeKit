# DS-01: the graded supply table, flat. Facts come from docs/data-sources/inventory.md, section 0.
# Upper case = full supply (filled dot), lower case = partial (ring).
import blueprint as bp
bp.H = 1290
from blueprint import ACC, INK
import uml
from uml import TINT, text

o = uml.sheet('Free data sources, graded')
CODES = 'PSERFQVDNMXCTIKGAYW'
NAMES = {'P': 'prices', 'S': 'sector, type', 'E': 'ETF holdings', 'R': 'risk-free', 'F': 'statements', 'Q': 'ratios',
         'V': 'FCF, EPS, shares', 'D': 'dividends', 'N': 'peers', 'M': 'macro', 'X': 'recession flag', 'C': 'commodities',
         'T': 'trade flows', 'I': 'institutional', 'K': 'insiders', 'G': 'filings', 'A': 'analyst ratings',
         'Y': 'earnings calendar', 'W': 'news sentiment'}
# (source, grade, cost, rate, volume, history, terms, supply)
ROWS = [
    ('SEC EDGAR', 'A', '$0, no key', '10/s, UA contact', 'none, nightly bulk', '2009+ (XBRL)', 'public domain', 'FVDNIKGES'),
    ('US Treasury', 'A', '$0, no key', 'none stated', 'none', 'decades', 'no restriction', 'RM'),
    ('OpenFIGI', 'A', '$0, optional key', '25/min (250 key)', '10 jobs/request', 'n/a', 'free', ''),
    ('Tiingo', 'A-', '$0, key', '50/hour', '1k/day, 500 sym/mo', 'decades (unverified)', 'personal use', 'PD'),
    ('EIA', 'B+', '$0, key', 'not stated', 'not stated', 'decades', 'free', 'C'),
    ('Alpaca', 'B+', '$0, paper account', '200/min', 'none', '7+ years', 'personal, no redistr.', 'PD'),
    ('Finnhub', 'B+', '$0, key', '60/min', 'none', 'varies', 'personal use', 'AKGNQsy'),
    ('BLS / BEA', 'B', '$0, key', '500/day (BLS)', '20 years/call', 'decades', 'public', 'M'),
    ('UN Comtrade', 'B', '$0, key', '100-500/day', '100k records/call', '1962+', 'non-commercial', 'T'),
    ('World Bank', 'B', '$0, no key', 'not stated', 'none', 'decades, annual', 'CC BY 4.0', 'M'),
    ('French / Shiller', 'B', '$0, static files', 'n/a', 'n/a', '1926+ / 1871+', 'academic, cite', 'Mx'),
    ('Issuer CSVs', 'B-', '$0', 'none', 'one file/fund', 'current only', 'terms unknown', 'E'),
    ('Yahoo', 'C+', '$0, no key', 'unpublished, 429s', 'none', 'decades / 4-5 yrs', 'personal, unofficial', 'PSFDIKAYe'),
    ('FRED', 'C', '$0, key', '120/min', 'none', 'decades', 'no storing', 'MXC'),
    ('Alpha Vantage', 'C', '$0, key', 'not stated', '25/day', 'compact only', 'not read', 'Yfvemc'),
    ('OECD', 'C', '$0, no key', '20-60/hour', 'none', 'decades', 'not read', 'M'),
    ('Stooq', 'C', '$0, CAPTCHA key', 'unpublished cap', 'none', 'decades', 'unofficial', 'p'),
    ('IMF', 'C-', '$0, maybe account', 'not stated', 'not stated', 'decades', 'API migrating', 'Mct'),
    ('GDELT', 'D', '$0, no key', 'informal', 'huge raw files', '2013+', 'free, cite', 'w'),
    ('Massive', 'D', '$0, key', '5/min', 'none', '2 years', 'not read', 'Rpds'),
    ('FMP', 'D?', '$0, key', 'not stated', '250/day', 'unverified', 'not read', 'ps'),
    ('SimFin', 'D', '$0, key', '2/s', '500 credits/month', '5-7 yrs, delayed', 'delete on expiry', 'f'),
    ('Twelve Data', 'D', '$0, key', '8/min', '800/day', 'unverified', 'not read', 'p'),
    ('Nasdaq Data Link', 'D', '$0, key', 'unverified', 'unverified', 'varies', 'varies', 'mc'),
    ('EODHD', 'F', '$0, key', '20/min', '20/day', '1 year', 'not read', 'pd'),
    ('Marketstack', 'F', '$0, key', 'n/a', '100/month', '1 year', 'non-commercial', 'p'),
    ('Intrinio', 'F', 'no free tier', '-', '-', '-', '-', ''),
    ('IEX Cloud', 'F', 'shut down 2024', '-', '-', '-', '-', ''),
]
X0, Y0, RH, HH = 60, 196, 27, 124
W = [168, 58, 140, 142, 156, 150, 158]          # text columns
CW = 25                                         # one demand column
xs = [X0]
for w in W:
    xs.append(xs[-1] + w)
cx0 = xs[-1]
right = cx0 + CW * len(CODES)
h = HH + RH * len(ROWS)

o.append(text(60, 178, 'SUPPLY: WHICH SOURCE CAN FILL WHICH DEMAND, AND AT WHAT CONSTRAINT', 't'))
o.append(f'<rect x="{X0}" y="{Y0}" width="{right-X0}" height="{h}" style="fill:#fff;stroke:{INK};stroke-width:1.5"/>')
for r, row in enumerate(ROWS):  # grade A rows carry the plan, so they get the tint
    if row[1].startswith('A'):
        o.append(f'<rect x="{X0}" y="{Y0+HH+r*RH}" width="{right-X0}" height="{RH}" style="fill:{TINT}"/>')
# dropped demand: W (news sentiment)
wx = cx0 + CODES.index('W') * CW
o.append(f'<rect x="{wx}" y="{Y0}" width="{CW}" height="{h}" style="fill:#f3f3f4"/>')
o.append(f'<line x1="{X0}" y1="{Y0+HH}" x2="{right}" y2="{Y0+HH}" style="stroke:{INK};stroke-width:1.5"/>')
o.append(f'<line x1="{cx0}" y1="{Y0}" x2="{cx0}" y2="{Y0+h}" style="stroke:{INK};stroke-width:1.2"/>')
for i, t in enumerate(['SOURCE', 'GRADE', 'COST', 'RATE', 'VOLUME', 'HISTORY', 'STORAGE / TERMS']):
    o.append(text(xs[i] + 10, Y0 + HH - 14, t, 't', style='font-size:10.5px;letter-spacing:1.2px'))
for j, c in enumerate(CODES):
    x = cx0 + j * CW + CW / 2
    col = '#9a9ca6' if c == 'W' else INK
    o.append(text(x, Y0 + HH - 14, c, 'h', 'middle', f'font-size:13px;fill:{col}'))
    o.append(f'<text transform="translate({x+3.5},{Y0+HH-32}) rotate(-90)" class="s" style="font-size:9.5px;fill:{col}">{NAMES[c]}</text>')
for r, (src, g, *cells, sup) in enumerate(ROWS):
    y = Y0 + HH + r * RH
    if r:
        o.append(f'<line x1="{X0}" y1="{y}" x2="{right}" y2="{y}" style="stroke:#d8d8db;stroke-width:1"/>')
    o.append(text(X0 + 10, y + 18, src, style=f'font-size:12.5px;font-weight:600;fill:{INK}'))
    gc = ACC if g.startswith('A') else INK
    o.append(f'<rect x="{xs[1]+10}" y="{y+5}" width="34" height="17" rx="8.5" style="fill:#fff;stroke:{gc};stroke-width:1.2"/>'
             + text(xs[1] + 27, y + 17.5, g, 'h', 'middle', f'font-size:11px;fill:{gc}'))
    for c, v in enumerate(cells):
        o.append(text(xs[c + 2] + 10, y + 18, v, style=f'font-size:12px;fill:{INK}'))
    for j, code in enumerate(CODES):
        x, yc = cx0 + j * CW + CW / 2, y + RH / 2
        if code in sup:
            o.append(f'<circle cx="{x}" cy="{yc}" r="5.5" style="fill:{ACC if g.startswith("A") else INK}"/>')
        elif code.lower() in sup:
            o.append(f'<circle cx="{x}" cy="{yc}" r="4.8" style="fill:#fff;stroke:{INK};stroke-width:1.4"/>')
        elif src != 'OpenFIGI':
            o.append(f'<circle cx="{x}" cy="{yc}" r="1.3" style="fill:#bdbdc4"/>')
    if src == 'OpenFIGI':
        o.append(text(cx0 + 12, y + 18, 'identifier map only: CUSIP to ticker, for I and E', style='font-size:12px'))

# key strip
yk = Y0 + h + 40
o.append(text(60, yk, 'HOW TO READ IT', 't'))
o.append(f'<circle cx="66" cy="{yk+22}" r="5.5" style="fill:{INK}"/>' + text(80, yk + 26, 'Full supply of that demand'))
o.append(f'<circle cx="66" cy="{yk+44}" r="4.8" style="fill:#fff;stroke:{INK};stroke-width:1.4"/>' + text(80, yk + 48, 'Partial supply'))
o.append(f'<rect x="60" y="{yk+58}" width="14" height="14" style="fill:{TINT};stroke:{ACC}"/>' + text(80, yk + 70, 'Grade A: official, free, deep, cacheable'))
o.append(f'<rect x="60" y="{yk+80}" width="14" height="14" style="fill:#f3f3f4;stroke:#9a9ca6"/>' + text(80, yk + 92, 'W: dropped from scope'))
o.append(text(420, yk, 'BINDING CONSTRAINTS AFTER CACHING', 't'))
for i, s in enumerate(['Tiingo: 500 symbols a month caps the price universe.',
                       'Alpha Vantage: 25 calls a day makes it a slow backfill only.',
                       'FRED: the terms forbid storing, so it is never a stored source.',
                       'N-PORT: the 60-day lag limits how fresh ETF holdings are.']):
    o.append(text(420, yk + 26 + i * 22, s, style=f'font-size:12.5px;fill:{INK}'))
o.append(text(900, yk, 'SOURCE OF THE GRADES', 't'))
for i, s in enumerate(['docs/data-sources/inventory.md, researched 2026-11-21.',
                       'Provider terms change. Read them again before you build on a row.',
                       'Grade: A best, F not usable.']):
    o.append(text(900, yk + 26 + i * 22, s, style=f'font-size:12.5px;fill:{INK}'))
uml.finish(o, 'ds-supply', 'DS-01 SUPPLY', view='FLAT')
