# DS-06: infrastructure and stack. 3D at a free camera: icons lie on the roofs, every label is a flat billboard.
# Facts: user decisions (Vercel, Render, Prisma Postgres), caching.md section 5, and the modular-monolith plan
# (docs/superpowers/plans/2026-11-19-java-modular-monolith.md: modules, render.yaml with a private RAG service).
import blueprint as bp
bp.H = 1180
bp.VIEW = (32, 40)
from blueprint import ACC, INK, T, block, face, lu, si, wire, iso
import uml
from uml import TINT, note, text

o = uml.sheet('Where it runs')
PW, PD = 1320, 520
bp.fit(PW, PD, (60, 175, 1300, 800), h=200)

def floor(x0, y0, w, d, label):
    return (block(x0, y0, w, d, -T, T) + face(0) + f'<rect x="{x0}" y="{y0}" width="{w}" height="{d}" fill="url(#minor)"/></g>')

def box(x, y, w, d, z, h, icon_svg, acc=False):
    return block(x, y, w, d, z, h, TINT if acc else '#fff', 'acc' if acc else 'ink') + face(z + h) + \
        f'<g transform="translate({x + w/2 - 24},{y + d/2 - 24})">{icon_svg}</g></g>'

def label(x, y, z, title, sub='', dx=0, dy=0, anchor='middle', acc=False):
    X, Y = iso(x, y, z)
    col = f'fill:{ACC};' if acc else ''
    return (text(X + dx, Y + dy, title, 'h', anchor, f'{col}font-size:14px;{uml.HALO}') +
            (text(X + dx, Y + dy + 17, sub, anchor=anchor, style=f'font-size:12px;{uml.HALO}') if sub else ''))

ZONES = [(0, 170, 140, 180, 'CLIENT'), (200, 140, 220, 240, 'VERCEL'), (480, 0, 520, 520, 'RENDER'),
         (1060, 0, 260, 520, 'DATA')]
for z in ZONES:
    o.append(floor(*z))
# zone names on the floor, flat
for x0, y0, w, d, name in ZONES:
    X, Y = iso(x0 + 8, y0 + d - 6, 0)
    o.append(text(X, Y + 18, name, 't', style=f'font-size:12px;{uml.HALO}'))

# wires on the floor (drawn last, they lie in front)
o.append(face(0) + wire('M120 260 H218') + wire('M400 220 H528') +
         wire('M790 140 H1098') + wire('M790 220 H940 V390 H1098') +
         wire('M660 270 V358', 'stroke-dasharray:6 4') + '</g>')

# blocks, back to front
o.append(box(1100, 40, 180, 180, 0, 40, si('prisma', 0, 0, 48), acc=True))
o.append(box(1100, 300, 180, 180, 0, 26, lu('globe', 0, 0, 48)))
# monolith: five stacked module slabs, outermost at the bottom
MODS = [('marketdata-api', 'port, canonical records'), ('marketdata', 'FMP, Yahoo adapters, Caffeine'),
        ('risk', 'portfolio and risk, JDBC'), ('valuation', 'DCF, DDM, Lynch, peers'), ('app', 'Spring Boot entry point')]
mx, my, mw, md = 530, 40, 260, 230
for i, (name, sub) in enumerate(MODS):
    z = i * 42
    acc = name == 'app'
    o.append(block(mx, my, mw, md, z, 12, TINT if acc else '#fff', 'acc' if acc else 'ink'))
for i, (name, sub) in enumerate(MODS):
    X, Y = iso(mx + mw, my, i * 42 + 6)
    LX = 1330
    LY = 300 + (4 - i) * 44
    o.append(f'<path d="M{X+4:.1f} {Y:.1f} H{LX-60} L{LX-8} {LY-6}" class="thin" style="stroke-dasharray:2 3"/>'
             f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="2.5" fill="{INK}"/>'
             + text(LX, LY - 2, name, 'h', style=f'font-size:13.5px;{"fill:" + ACC if name == "app" else ""}')
             + text(LX, LY + 14, sub, style='font-size:11.5px'))
o.append(face(4 * 42 + 12) + f'<g transform="translate({mx + 20},{my + 20})">{si("springboot", 0, 0, 40)}</g></g>')
o.append(box(530, 360, 260, 120, 0, 30, si('fastapi', 0, 0, 48)))
o.append(box(220, 190, 180, 140, 0, 30, si('vercel', 0, 0, 48)))
o.append(box(20, 210, 100, 100, 0, 30, lu('app-window', 0, 0, 48)))

# billboards
o.append(label(70, 210, 30, 'BROWSER', 'investor, visitor', dy=-60))
o.append(label(310, 190, 30, 'FRONTEND', 'React 19, Vite, Tailwind 4', dy=-70))
o.append(text(1330, 220, 'BACKEND MODULES', 'h', style='font-size:14px') + text(1330, 237, 'Java 21, Spring Boot 3.3,') + text(1330, 253, 'one Maven modular monolith'))
o.append(label(790, 420, 30, 'HYBRID-RAG', 'Python 3.11, FastAPI', dx=20, dy=-4, anchor='start'))
o.append(label(1190, 40, 40, 'PRISMA POSTGRES', 'store of record', dy=-40, acc=True))
o.append(label(1280, 390, 26, 'DATA SOURCES', 'via the waterfall', dx=18, dy=10, anchor='start'))
for x, y, s in ((170, 260, 'HTTPS'), (465, 220, 'JSON API'), (945, 140, 'JDBC + Flyway'), (1030, 390, 'HTTP, per source'),
                (600, 315, 'private network')):
    X, Y = iso(x, y, 0)
    o.append(text(X, Y + 20, s, anchor='middle', style=f'font-size:11.5px;{uml.HALO}'))

# notes strip
ys = 830
o.append(text(60, ys, 'WHAT RUNS WHERE', 't'))
for i, s in enumerate(['Vercel serves the React front end as a static build.',
                       'Render runs the backend: one Spring Boot jar from five Maven modules.',
                       'Render runs hybrid-rag as a separate, private Python service.',
                       'Prisma Postgres holds portfolios and the market-data store.',
                       'The backend uses plain JDBC and Flyway on the direct connection string.',
                       'It does not use the Prisma ORM.']):
    o.append(text(60, ys + 26 + i * 21, s, style='font-size:12.5px;fill:#0a0b1f'))
o.append(text(640, ys, 'FREE-TIER LIMITS THAT SHAPE THE DESIGN', 't'))
for i, s in enumerate(['Prisma Postgres: 200k operations a month, 2 GB storage.',
                       'Render free web service: sleeps after about 15 minutes idle.',
                       'So: Caffeine in front of every read, batched inserts,',
                       'a seed sized to the storage cap, refresh on visit.',
                       'Prices change. See each vendor’s pricing page.']):
    o.append(text(640, ys + 26 + i * 21, s, style='font-size:12.5px;fill:#0a0b1f'))
uml.finish(o, 'ds-infra', 'DS-06 INFRA', view='AXO 32/40')
