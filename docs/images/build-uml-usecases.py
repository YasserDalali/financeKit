# UML-01: use cases, flat 2D. Lenses come from the landing copy (landing/src/components/Features.tsx). Built endpoints:
# risk-management-ms PortfolioController (risk, beta, alpha, drawdown, correlation, look-through, ...), the valuation
# REST API on refactor/java-monolith, hybrid-rag POST /ingest and /query. Tenants, roles and the demo mode are designed.
import blueprint as bp
bp.H = 1080
from blueprint import ACC, lu
import uml
from uml import actor, line, note, package, system_box, text, usecase

o = uml.sheet('What FinRisk does, and for whom')
o.append('<rect x="280" y="180" width="900" height="720" style="fill:none;stroke:#0a0b1f;stroke-width:2"/>')
o.append(text(296, 203, 'FINRISK', 't'))
W = 260
PK = {  # name: (x, y, h, cases)
    'PUBLIC': (300, 220, 230, ['View the landing page', 'Request access', 'Try the demo (public data)']),
    'TENANT ADMIN (PLANNED)': (900, 220, 230, ['Invite members', 'Assign roles', 'Manage the tenant']),
    'PORTFOLIO': (300, 480, 400, ['Manage accounts', 'Record trades', 'View holdings and P&amp;L']),
    'FIVE LENSES': (600, 480, 400, ['Analyse portfolio risk', 'Read fundamentals', 'Value a stock',
                                     'Run a stress test', 'See market intelligence']),
    'DOCUMENTS': (900, 480, 400, ['Ingest documents', 'Ask documents']),
}
pos = {}
for name, (x, y, h, cases) in PK.items():
    o.append(package(x, y, W, h, name))
    gap = 66 if len(cases) > 3 else 54
    for i, c in enumerate(cases):
        cy = y + 64 + i * gap
        pos[c] = (x + W / 2, cy)
        o.append(usecase(x + W / 2, cy, c, rx=112))

o.append(note(600, 236, 260, ['A line to a package means', 'the actor can use every', 'use case inside it.']))

# actors
o.append(actor(160, 360, 'DEMO VISITOR', 'not signed in'))
o.append(line('M190 322 H298'))
o.append(actor(1330, 360, 'TENANT ADMIN', 'admin role'))
o.append(line('M1300 322 H1162'))
o.append(actor(730, 1010, '', ''))
o.append(text(757, 980, 'INVESTOR', 'h', style='font-size:14px') + text(757, 997, 'member of a tenant'))
o.append(line('M730 958 V924 H1030') + line('M430 924 H730'))
for x in (430, 730, 1030):
    o.append(line(f'M{x} 924 V882'))

# external systems
o.append(system_box(1220, 446, 230, 48, 'DATA SOURCES', lu('globe', 1232, 458, 24)))
o.append(text(1264, 512, 'through the waterfall', style='font-size:11.5px'))
o.append(line('M1220 466 H730 V478'))
o.append(system_box(1220, 600, 230, 48, 'HYBRID-RAG', lu('bot', 1232, 612, 24)))
ax, ay = pos['Ask documents']
o.append(line(f'M1220 624 L{ax + 112} {ay}'))
ix, iy = pos['Ingest documents']
o.append(line(f'M1220 616 L{ix + 112} {iy}'))

o.append(text(60, 940, 'STATUS', 't'))
for i, s in enumerate(['Built: risk metrics and portfolio CRUD (risk-management-ms), valuation API, hybrid-rag.',
                       'Designed: fundamentals, stress tests, market intelligence, the demo on public data.',
                       'Planned: tenants, roles and sign-in. Today the APIs have no login.']):
    o.append(text(60, 964 + i * 20, s, style='font-size:12.5px;fill:#0a0b1f'))
uml.finish(o, 'uml-usecases', 'UML-01 USE CASES')
