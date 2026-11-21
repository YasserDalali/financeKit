# UML-01: use cases, flat 2D. One actor, the investor. Portfolio data is private to each investor;
# market data is shared by all investors and stored once. Lenses come from the landing copy.
import blueprint as bp
bp.H = 980
from blueprint import lu
import uml
from uml import actor, line, note, package, system_box, text, usecase

o = uml.sheet('What FinRisk does, and for whom')
o.append('<rect x="300" y="180" width="840" height="560" style="fill:none;stroke:#0a0b1f;stroke-width:2"/>')
o.append(text(316, 203, 'FINRISK', 't'))
W, H = 360, 480
PK = {  # name: (x, cases)
    'PORTFOLIO · PRIVATE TO EACH INVESTOR': (330, ['Sign in', 'Manage accounts', 'Record trades',
                                                  'View holdings and P&amp;L']),
    'FIVE LENSES · SHARED MARKET DATA': (750, ['Analyse portfolio risk', 'Read fundamentals', 'Value a stock',
                                               'Run a stress test', 'See market intelligence']),
}
for name, (x, cases) in PK.items():
    o.append(package(x, 230, W, H, name))
    for i, c in enumerate(cases):
        o.append(usecase(x + W / 2, 300 + i * 82, c, rx=130))

# actor: one line into each package (the second runs under the system box)
o.append(actor(160, 470, 'INVESTOR', 'signed in'))
o.append(line('M190 432 H328'))
o.append(line('M160 560 V780 H930 V712'))

# external system
o.append(system_box(1200, 410, 240, 48, 'DATA SOURCES', lu('globe', 1212, 422, 24)))
o.append(text(1244, 476, 'through the waterfall', style='font-size:11.5px'))
o.append(line('M1200 432 H1112'))

o.append(note(300, 820, 840, ['Each investor sees only their own accounts, trades and holdings.',
                              'Market data (prices, filings, macro series) is shared by all investors and stored once.'],
              accent=True))
uml.finish(o, 'uml-usecases', 'UML-01 USE CASES')
