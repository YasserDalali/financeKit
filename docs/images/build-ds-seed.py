# DS-05: pre-seed and refresh on visit. Top (3D): what a visit starts. Bottom (flat): the seed universe and datasets.
# Facts come from docs/data-sources/caching.md, sections 6 and 7. Status: designed, not built.
import blueprint as bp
bp.H = 780
bp.VIEW, bp.TILE_H = (4, 70), 24
from blueprint import ACC, INK, badge, card, face, platform, tile, wire
import uml
from uml import note, text

o = uml.sheet('Pre-seed, then refresh on visit')
PW, PD = 1230, 380
bp.fit(PW, PD, (60, 190, 1545, 600), h=24)
o.append(text(60, 178, 'WHAT A VISIT STARTS. NO CRON: WORK RUNS ONLY WHILE SOMEONE USES THE APP', 't'))
o.append(platform(0, PW, PD))
R1, R2, D = 25, 215, 150
tiles = [
    (0, R1, 160, D, card('user-round', 'VISIT', 'wakes Render'), False),
    (230, R1, 220, D, card('clock', 'WAKE-UP CHECK', 'ApplicationReady', lines=['reads fetch_log']), False),
    (520, R1, 200, D, card('cpu', 'REFRESH POOL', '2 threads, fixed'), False),
    (790, R1, 200, D, card('lock', 'SINGLE FLIGHT', 'advisory lock', lines=['per resource + key']), False),
    (1060, R1, 170, D, card('gauge', 'BUDGETS', 'per source', lines=['token bucket', 'monthly counter']), False),
    (0, R2, 160, D, card('app-window', 'REQUEST', 'one resource'), False),
    (230, R2, 220, D, card('timer', 'STALE CHECK', 'fresh, stale, empty', lines=['stale: serve now,', 'queue a refresh']), False),
    (790, R2, 200, D, card('database', 'POSTGRES', 'rows + fetch_log', ACC, lines=['progress per key:', 'resumable']), True),
    (1060, R2, 170, D, card('network', 'WATERFALL', 'live layers'), False),
]
for x, y, w, d, inner, acc in sorted(tiles, key=lambda t: bp.depth(t[0], t[1])):
    o.append(tile(x, y, w, d, 0, inner, acc))
m1, m2 = R1 + 65, R2 + 65
o.append(face(bp.TILE_H) +
         wire(f'M160 {m1} H228') + wire(f'M450 {m1} H518') + wire(f'M720 {m1} H788') + wire(f'M990 {m1} H1058') +
         wire(f'M1145 {R1+D} V{R2-2}') + wire(f'M1060 {m2} H992') +
         wire(f'M160 {m2} H228') + wire(f'M450 {m2+20} H620 V{R1+D+2}', 'stroke-dasharray:6 4') +
         badge(1, 194, m1) + badge(2, 484, m1) + badge(3, 754, m1) + badge(4, 1024, m1) + badge(5, 1145, 195)
         + badge(6, 1026, m2) + badge(7, 194, m2) + badge(8, 535, m2 + 20) + '</g>')

ky = 640
o.append(text(60, ky, 'KEY', 't'))
steps = ['A visit wakes the sleeping Render instance.', 'One task reads fetch_log and finds work past next_due.',
         'Refreshes run on a fixed pool of 2 threads.', 'An advisory lock stops a second fetch of the same key.',
         'An empty source budget skips that layer, as if it were down.', 'The waterfall writes rows and progress to Postgres.',
         'A request checks the stored row first.', 'Stale but inside max stale: serve now, queue a refresh.']
for i, s in enumerate(steps):
    col, row = divmod(i, 4)
    x, y = 60 + col * 560, ky + 26 + row * 22
    o.append(text(x, y, f'{i+1}', style=f'font-size:12.5px;font-weight:700;fill:{ACC}') + text(x + 22, y, s, style='font-size:12.5px;fill:#0a0b1f'))
uml.finish(o, 'ds-seed', 'DS-05 SEED', view='AXO 4/70')
