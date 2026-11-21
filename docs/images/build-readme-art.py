# README art for FinRisk in the blueprint style: the hero banner and the pill badges. Writes SVGs into readme/ and renders
# each to PNG with headless Chrome (PNG keeps the Inter font; GitHub would fall back to another font in an SVG).
import os, subprocess
import blueprint as bp
from blueprint import write_text
bp.OX, bp.OY, bp.K = 1170, 262, 0.5
from blueprint import ACC, INK, PD, SOFT, Z, iso, lu, risers, slab, tile

OUT = os.path.join(bp.HERE, 'readme')
os.makedirs(OUT, exist_ok=True)

def head(w, h):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" font-family="Inter, Helvetica, Arial, sans-serif">
<defs>
<pattern id="minor" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="#eceeed" stroke-width="0.6"/></pattern>
<pattern id="major" width="100" height="100" patternUnits="userSpaceOnUse"><rect width="100" height="100" fill="url(#minor)"/><path d="M100 0H0V100" fill="none" stroke="#d9dcdb" stroke-width="0.9"/></pattern>
</defs>
<style>
.ink{{stroke:{INK};fill:none;stroke-width:1.5;stroke-linejoin:round}}.thin{{stroke:{INK};fill:none;stroke-width:1}}
.acc{{stroke:{ACC};fill:none;stroke-width:2}}.dash{{stroke:{INK};fill:none;stroke-width:1;stroke-dasharray:4 3}}
.t{{fill:{INK};font-size:11px;letter-spacing:1.6px;font-weight:600}}.s{{fill:{SOFT};font-size:12px}}
</style>'''

def render(name, w, h):
    """Render the SVG to PNG. Transparent background, so rounded corners show the page behind it."""
    for suffix in ('',):
        svg, png = os.path.join(OUT, name + suffix + '.svg'), os.path.join(OUT, name + suffix + '.png')
        subprocess.run(['google-chrome', '--headless', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
                        '--default-background-color=00000000', '--force-device-scale-factor=2', f'--window-size={w},{h}',
                        f'--screenshot={png}', f'file://{svg}'], check=True, capture_output=True)

# --- hero -----------------------------------------------------------------
W, H = 1600, 560
o = [head(W, H), f'<clipPath id="heroclip"><rect width="{W}" height="{H}" rx="24"/></clipPath><g clip-path="url(#heroclip)">',
     f'<rect width="{W}" height="{H}" fill="#fff"/><rect width="{W}" height="{H}" fill="url(#major)"/>',
     f'<rect x="10" y="10" width="{W-20}" height="{H-20}" rx="16" class="ink"/>',
     '<text x="60" y="90" class="t">FINRISK · SHEET 00</text>',
     f'<text x="56" y="190" fill="{INK}" font-size="104" font-style="italic" font-family="\'EB Garamond\', Georgia, serif" letter-spacing="-2">FinRisk</text>',
     f'<text x="60" y="246" fill="{INK}" font-size="24">Portfolio risk and stock valuation</text>',
     f'<text x="60" y="278" fill="{INK}" font-size="24">on free market data, heavily cached.</text>']

TOP, MID, BOT = Z
icons = {TOP: ('app-window', 'chart-line', 'scale'), MID: ('gauge', 'calculator', 'network'),
         BOT: ('database', 'cpu', 'globe')}
for z in (BOT, MID, TOP):  # bottom first: upper slabs hide what is under them
    o.append(slab(z))
    for x, ic in zip((15, 165, 315), icons[z]):
        o.append(tile(x, 30, 130, 140, z, lu(ic, 37, 42, 56, ACC if ic == 'network' else INK), ic == 'network'))
    if z != TOP:
        o.append(risers(z + bp.GAP))

for z, name in ((TOP, 'Frontend · Vercel'), (MID, 'Backend · Render'), (BOT, 'Data · Prisma Postgres')):  # leader lines, like an engineering sheet
    X, Y = iso(0, PD, z)
    o.append(f'<line x1="760" y1="{Y:.1f}" x2="{X - 5:.1f}" y2="{Y:.1f}" class="thin"/>'
             f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="2.5" fill="{INK}"/>'
             f'<text x="760" y="{Y + 22:.1f}" fill="{INK}" font-size="18">{name}</text>')

o.append(f'<line x1="60" y1="470" x2="{W-60}" y2="470" class="thin"/>')
# Footer row, like a drawing's notes strip: (x, y, text) so columns line up without padding spaces
foot = [(60, 500, 'FIVE LENSES ON A PORTFOLIO,'), (60, 517, 'ONE JAVA MODULAR MONOLITH.'),
        (560, 500, 'BUILT ON:'), (680, 500, '→ SPRING BOOT'), (680, 517, '→ POSTGRES'), (680, 534, '→ REACT'),
        (1000, 500, 'DATA  →'), (1090, 500, 'ONE WATERFALL PER RESOURCE,'), (1090, 517, 'FREE SOURCES, STORED ONCE.')]
for x, y, line in foot:
    o.append(f'<text x="{x}" y="{y}" class="t" style="font-size:12px;letter-spacing:2.4px">{line}</text>')
o.append('</g></svg>')
write_text(os.path.join(OUT, 'hero'), '\n'.join(o))
render('hero', W, H)

# --- pills ----------------------------------------------------------------
# (label, icon kind, icon name). Brand marks come from Simple Icons, the rest from Lucide. All drawn in ink.
# Four rows: platform, backend, frontend, services. Brand marks from Simple Icons, the rest from Lucide.
PILL_ROWS = [
    [('Render', 'si', 'render'), ('Vercel', 'si', 'vercel'), ('Prisma Postgres', 'si', 'prisma'), ('Docker', 'si', 'docker')],
    [('Java 21', 'si', 'openjdk'), ('Spring Boot 3.3', 'si', 'springboot'), ('Maven', 'si', 'apachemaven'),
     ('PostgreSQL', 'si', 'postgresql'), ('Flyway', 'si', 'flyway'), ('Caffeine', 'lu', 'cpu'), ('JUnit 5', 'si', 'junit5')],
    [('React 19', 'si', 'react'), ('Vite', 'si', 'vite'), ('Tailwind CSS 4', 'si', 'tailwindcss'), ('TypeScript', 'si', 'typescript')],
    [('Python 3.11', 'si', 'python'), ('FastAPI', 'si', 'fastapi'), ('LangChain', 'si', 'langchain'),
     ('FAISS + BM25', 'lu', 'search'), ('Free data sources', 'lu', 'globe')],
]
PILLS = [p for row in PILL_ROWS for p in row]
for f in os.listdir(OUT):  # drop pills that are no longer in the list
    if f.startswith('pill-'):
        os.remove(os.path.join(OUT, f))
for label, kind, icon in PILLS:
    text = label.upper()
    w, h = int(62 + len(text) * 9.4), 40
    # ponytail: 2.2 px icon strokes looked heavy at pill size; Lucide icons draw at 1.5 px here, brand marks
    # are solid shapes, so they shrink to 18 px to sit lighter.
    bp.ICON_PX = 1.5
    mark = bp.si(icon, 16, 11, 18) if kind == 'si' else lu(icon, 15, 10, 20)
    svg = (head(w, h) + f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="19" class="ink" style="fill:#fff"/>' + mark +
           f'<text x="44" y="24.5" class="t" style="font-size:12px;letter-spacing:1.8px">{text}</text></svg>')
    slug = label.lower().replace(' + ', '-').replace(' ', '-').replace('.', '')
    write_text(os.path.join(OUT, f'pill-{slug}'), svg)
    render(f'pill-{slug}', w, h)
print('ok', sorted(os.listdir(OUT)))
