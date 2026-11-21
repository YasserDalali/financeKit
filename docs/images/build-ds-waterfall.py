# DS-02: the source waterfall. Top (flat Sankey): lens -> resource -> source; band width = expected share of
# answers each layer gives, p_k * prod(1 - p_j) over the layers before it, with p = reliability x coverage.
# Bottom (flat): the order for every resource, computed by docs/data-sources/waterfall.py, and the rules.
# Status: designed, not built. The code today has one global order, FMP then Yahoo (FailoverMarketData).
import os, sys
import blueprint as bp
bp.H = 1400
bp.VIEW = (4, 40)
from blueprint import ACC, INK
import uml
from uml import TINT, note, text
sys.path.insert(0, os.path.join(bp.HERE, '..', 'data-sources'))
import waterfall as wf

o = uml.sheet('The source waterfall')
o.append(text(60, 176, 'WHO ANSWERS WHAT. BAND WIDTH = EXPECTED SHARE OF ANSWERS', 't'))

def p_of(s, r):
    return wf.RELIABILITY[wf.SOURCES[s][0]] * wf.SUPPLY[s][r]

Y0, Y1 = 200, 640
X_LENS, X_RES, X_SRC, NW = 230, 640, 1180, 14
res = [(lens, r) for lens, items in wf.CONTRACTS.items() for r, _ in items]
gap = 5
unit = (Y1 - Y0 - gap * (len(res) - 1)) / len(res)

flows = []  # (resource index, source, share, rank)
for i, (_, r) in enumerate(res):
    left = 1.0
    for k, s in enumerate(wf.waterfall(r)):
        share = left * p_of(s, r)
        flows.append((i, s, share, k))
        left -= share
    flows.append((i, 'Unanswered', left, 9))

tot = {}
for _, s, sh, _ in flows:
    tot[s] = tot.get(s, 0) + sh
OTHER = 'Other fallbacks'
small = sorted(s for s in tot if s != 'Unanswered' and tot[s] < 0.12)
flows = [(i, OTHER if s in small else s, sh, k) for i, s, sh, k in flows]
tot = {}
for _, s, sh, _ in flows:
    tot[s] = tot.get(s, 0) + sh
srcs = sorted((s for s in tot if s not in ('Unanswered', OTHER)), key=lambda s: -tot[s]) + [OTHER, 'Unanswered']
sgap = 14
sunit = (Y1 - Y0 - sgap * (len(srcs) - 1)) / len(res)
sy, y = {}, Y0
for s in srcs:
    sy[s] = y; y += tot[s] * sunit + sgap

def band(x0, a0, b0, x1, a1, b1, style):
    m = (x0 + x1) / 2
    return (f'<path d="M{x0} {a0:.1f} C{m} {a0:.1f} {m} {a1:.1f} {x1} {a1:.1f} L{x1} {b1:.1f} '
            f'C{m} {b1:.1f} {m} {b0:.1f} {x0} {b0:.1f} Z" style="{style}"/>')

# lens nodes and lens -> resource bands
ry = [Y0 + i * (unit + gap) for i in range(len(res))]
lenses = list(wf.CONTRACTS)
ly, y = {}, Y0 + 20
lgap = (Y1 - Y0 - 40 - len(res) * unit) / (len(lenses) - 1)
for lens in lenses:
    n = sum(1 for l, _ in res if l == lens)
    ly[lens] = y; y += n * unit + lgap
cur = dict(ly)
for i, (lens, r) in enumerate(res):
    o.append(band(X_LENS + NW, cur[lens], cur[lens] + unit, X_RES, ry[i], ry[i] + unit,
                  f'fill:{INK};fill-opacity:.06;stroke:none'))
    cur[lens] += unit
for lens in lenses:
    n = sum(1 for l, _ in res if l == lens)
    o.append(f'<rect x="{X_LENS}" y="{ly[lens]:.1f}" width="{NW}" height="{n*unit:.1f}" style="fill:{INK}"/>')
    o.append(text(X_LENS - 12, ly[lens] + n * unit / 2 + 4, lens.upper(), 'h', anchor='end', style='font-size:13px'))

# resource -> source bands, stacked at both ends in resource order
rcur = list(ry)
scur = dict(sy)
for i, s, sh, k in sorted(flows, key=lambda f: (srcs.index(f[1]), f[0])):
    pass
for i, s, sh, k in flows:  # resource side, in layer order
    h = sh * unit
    f = list(flows)
order = sorted(range(len(flows)), key=lambda j: (srcs.index(flows[j][1]), flows[j][0]))
src_pos = {}
for j in order:
    i, s, sh, k = flows[j]
    src_pos[j] = scur[s]; scur[s] += sh * sunit
for j, (i, s, sh, k) in enumerate(flows):
    if sh < 1e-4:
        continue
    a0 = rcur[i]; rcur[i] += sh * unit
    a1 = src_pos[j]
    if s == 'Unanswered':
        st = f'fill:none;stroke:{INK};stroke-opacity:.35;stroke-dasharray:3 3;stroke-width:.8'
    elif k == 0:
        st = f'fill:{ACC};fill-opacity:.30;stroke:none'
    else:
        st = f'fill:{INK};fill-opacity:.16;stroke:none'
    o.append(band(X_RES + NW, a0, a0 + sh * unit, X_SRC, a1, a1 + sh * sunit, st))

for i, (_, r) in enumerate(res):
    o.append(f'<rect x="{X_RES}" y="{ry[i]:.1f}" width="{NW}" height="{unit:.1f}" style="fill:{INK}"/>')
    o.append(text(X_RES + NW + 8, ry[i] + unit / 2 + 4, r, style=f'{uml.MONO};font-size:11px;fill:{INK}'))
for s in srcs:
    h = tot[s] * sunit
    fill = INK if s != 'Unanswered' else '#fff'
    o.append(f'<rect x="{X_SRC}" y="{sy[s]:.1f}" width="{NW}" height="{max(h,1.5):.1f}" style="fill:{fill};stroke:{INK};stroke-width:.8"/>')
    if s == OTHER:
        o.append(text(X_RES, Y1 + 34, 'Other fallbacks: ' + ', '.join(small) + '.', style='font-size:11.5px'))
    o.append(text(X_SRC + NW + 10, sy[s] + max(h, 1.5) / 2 + 4, f'{s}', 'h', style='font-size:12.5px')
             + text(X_SRC + NW + 160, sy[s] + max(h, 1.5) / 2 + 4, f'{tot[s]:.2f}', style=f'{uml.MONO};font-size:11.5px'))

# legend
lx, lyy = X_SRC + 10, 182
o.append(f'<rect x="{lx-200}" y="{lyy-10}" width="22" height="10" style="fill:{ACC};fill-opacity:.30"/>'
         + text(lx - 172, lyy, '1st layer', style='font-size:11.5px')
         + f'<rect x="{lx-100}" y="{lyy-10}" width="22" height="10" style="fill:{INK};fill-opacity:.16"/>'
         + text(lx - 72, lyy, 'fallback', style='font-size:11.5px')
         + f'<path d="M{lx} {lyy-5} h22" style="stroke:{INK};stroke-dasharray:3 3;stroke-width:.8"/>'
         + text(lx + 28, lyy, 'unanswered', style='font-size:11.5px')
         + text(X_SRC + NW + 160, lyy, 'answers', 't', style='font-size:10.5px'))

# --- scoring rule (flat) ---------------------------------------------------------
yr = 700
o.append(text(60, yr, 'SCORE: SMITH’S RULE FOR SEQUENTIAL SEARCH', 't'))
o.append(f'<rect x="60" y="{yr+14}" width="420" height="118" style="fill:{TINT};stroke:{ACC};stroke-width:1.5"/>')
for i, (a, b) in enumerate([('p =', 'reliability(grade) × coverage'), ('c =', '1 + quota pressure + cache penalty'),
                            ('order =', 'descending p / c')]):
    o.append(text(76, yr + 44 + i * 30, a, style=f'{uml.MONO};font-size:14px;font-weight:700;fill:{ACC}')
             + text(150, yr + 44 + i * 30, b, style=f'{uml.MONO};font-size:13px;fill:{INK}'))
for i, s in enumerate(['Each try succeeds with chance p and costs c.',
                       'Descending p/c gives the lowest expected cost',
                       'until one layer answers.',
                       'Coverage: full 1.0, IEX-only 0.75, partial 0.5.',
                       'Cache penalty 2: FRED, whose terms forbid storing.',
                       'Order is configuration, generated by waterfall.py.']):
    o.append(text(60, yr + 160 + i * 21, s, style=f'font-size:12.5px;fill:{INK}'))
o.append(text(60, yr + 300, 'RELIABILITY BY GRADE', 't'))
for i, (g, r) in enumerate(list(wf.RELIABILITY.items())):
    x = 60 + (i % 6) * 70; y = yr + 326 + (i // 6) * 24
    o.append(text(x, y, f'{g}', 'h', style='font-size:12px') + text(x + 26, y, f'{r:.2f}', style=f'{uml.MONO};font-size:11.5px'))

# --- every resource (flat) ---------------------------------------------------------
xt = 530
o.append(text(xt, yr, 'ORDER FOR EVERY RESOURCE (SCORE IN BRACKETS)', 't'))
rows, tint = [], []
for lens, items in wf.CONTRACTS.items():
    for k, (res, _) in enumerate(items):
        cells = [f'{s} ({wf.score(s, res):.2f})' for s in wf.waterfall(res)]
        rows.append([lens.upper() if k == 0 else '', res] + cells + [''] * (4 - len(cells)))
        if res == 'prices':
            tint.append(len(rows) - 1)
svg, th = uml.grid(xt, yr + 14, [118, 150, 196, 182, 172, 192], ['LENS', 'RESOURCE', '1ST', '2ND', '3RD', '4TH'],
                   rows, rh=24, size=12, mono_cols=(1,), tint_rows=tint)
o.append(svg)

# --- rules (flat strip) -------------------------------------------------------------
yb = yr + 14 + th + 40
o.append(note(60, yb - 10, 440, ['Designed, not built. The code today has one', 'global order: FMP, then Yahoo (FailoverMarketData).'], accent=True))
o.append(text(xt, yb, 'RULES', 't'))
for i, s in enumerate(['A layer counts only if every required field is present. Otherwise the next layer runs.',
                       'One answer comes from one layer. Fields are never mixed across layers.',
                       'Missing optional fields stay null. The domain skips that metric and says so.']):
    o.append(text(xt, yb + 24 + i * 21, f'{i+1}. {s}', style=f'font-size:12.5px;fill:{INK}'))
uml.finish(o, 'ds-waterfall', 'DS-02 WATERFALL', view='AXO 4/40')
