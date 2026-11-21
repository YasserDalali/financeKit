# DS-04: what we store, how long it stays valid, and what we may keep. Top (3D): the read order with a stale fallback.
# Bottom (flat): storage classes, freshness per resource, rights tiers. Facts come from docs/data-sources/caching.md 1-4.
# Status: designed. Today only the Caffeine layer exists (CachingMarketData).
import blueprint as bp
bp.H = 700
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
uml.finish(o, 'ds-caching', 'DS-04 CACHING', view='AXO 14/46')
