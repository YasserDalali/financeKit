# Shared drawing kit for the 3D blueprint sheets. Rules: ../design-system.md
import math, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
SI = HERE + '/icons/simple-icons/'; LU = HERE + '/icons/lucide/'
ICON_PX = 2.2
INK, SOFT, ACC = '#0a0b1f', '#5b6270', '#0014dc'
SIDE_X, SIDE_Y = '#e4e4e6', '#f3f3f4'   # shaded faces: +x (right) darker, +y (left) lighter

def si(n, x, y, sz):
    d = re.search(r' d="([^"]+)"', open(SI + n + '.svg').read()).group(1)
    return f'<svg x="{x}" y="{y}" width="{sz}" height="{sz}" viewBox="0 0 24 24"><path fill="{INK}" d="{d}"/></svg>'

def lu(n, x, y, sz, color=INK):
    t = open(LU + n + '.svg').read().split('stroke-linejoin="round"')[1]
    inner = re.search(r'>\s*(<(?:path|ellipse|circle|rect|line|polyline)[\s\S]*)</svg>', t).group(1)
    return (f'<svg x="{x}" y="{y}" width="{sz}" height="{sz}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{round(ICON_PX*24/sz,3)}" stroke-linecap="round" stroke-linejoin="round">{inner}</svg>')

# --- isometric projection -------------------------------------------------
C, S = 0.866, 0.5
OX, OY = 688, 550
PW, PD, T = 460, 200, 10          # plane width (x), depth (y), slab thickness
TILE_H = 12                        # tile extrusion
GAP = 195                          # vertical distance between slabs
Z = (390, 195, 0)                  # top, middle, bottom slab
K = 1.0                            # plane scale; < 1 fits a wider plane on the sheet

# Camera. None = true isometric (CF-02, the README hero). Otherwise (azimuth, elevation) in degrees:
# azimuth turns the plane (0 = x axis flat across the sheet, 45 = isometric), elevation tilts the camera
# (35.26 = isometric, higher = more top-down). Keep azimuth inside (0, 90) so the +x and +y faces stay the visible ones.
VIEW = None
G = 1.2247449                      # sqrt(3/2): keeps a VIEW of (45, 35.26) the same size as the isometric default

def _axes():
    """Screen vectors of one unit along x, y and z (before K)."""
    if VIEW is None:
        return (C, S), (-C, S), (0, -1)
    az, el = (math.radians(a) for a in VIEW)
    return ((G * math.cos(az), G * math.sin(az) * math.sin(el)),
            (-G * math.sin(az), G * math.cos(az) * math.sin(el)),
            (0, -G * math.cos(el)))

def iso(x, y, z):
    if VIEW is None:
        return (OX + (x - y) * C * K, OY + ((x + y) * S - z) * K)
    ax, ay, az = _axes()
    return (OX + (x * ax[0] + y * ay[0]) * K, OY + (x * ax[1] + y * ay[1] + z * az[1]) * K)

def depth(x, y):
    """Sort key: larger is nearer the viewer, so draw it later."""
    if VIEW is None:
        return x + y
    ax, ay, _ = _axes()
    return x * ax[1] + y * ay[1]

def fit(pw, pd, box, h=24, xmin=0, ymin=0):
    """Set K, OX and OY so the plane (xmin..pw by ymin..pd, blocks up to h high) fills the screen box (x0, y0, x1, y1)."""
    global K, OX, OY
    K, OX, OY = 1.0, 0, 0
    pts_ = [iso(x, y, z) for x in (xmin, pw) for y in (ymin, pd) for z in (-T, h)]
    xs, ys = [p[0] for p in pts_], [p[1] for p in pts_]
    x0, y0, x1, y1 = box
    K = min((x1 - x0) / (max(xs) - min(xs)), (y1 - y0) / (max(ys) - min(ys)))
    OX = x0 - min(xs) * K + ((x1 - x0) - (max(xs) - min(xs)) * K) / 2
    OY = y0 - min(ys) * K

def pts(*p):
    return ' '.join(f'{a:.1f},{b:.1f}' for a, b in (iso(*q) for q in p))

def face(z):  # group whose children are drawn on the horizontal plane at height z
    if VIEW is None:
        return f'<g transform="matrix({C*K:g},{S*K:g},{-C*K:g},{S*K:g},{OX},{OY - z*K:g})">'
    ax, ay, az = _axes()
    return (f'<g transform="matrix({ax[0]*K:.5g},{ax[1]*K:.5g},{ay[0]*K:.5g},{ay[1]*K:.5g},'
            f'{OX:.2f},{OY + z * az[1] * K:.2f})">')

def block(x, y, w, d, z, h, top_fill='#fff', top_cls='ink'):
    """Extruded box: base at z, height h. Returns side faces + top face."""
    zt = z + h
    sx = f'<polygon points="{pts((x+w,y,z),(x+w,y+d,z),(x+w,y+d,zt),(x+w,y,zt))}" class="ink" style="fill:{SIDE_X}"/>'
    sy = f'<polygon points="{pts((x,y+d,z),(x+w,y+d,z),(x+w,y+d,zt),(x,y+d,zt))}" class="ink" style="fill:{SIDE_Y}"/>'
    top = f'<polygon points="{pts((x,y,zt),(x+w,y,zt),(x+w,y+d,zt),(x,y+d,zt))}" class="{top_cls}" style="fill:{top_fill}"/>'
    return sx + sy + top

def slab(z):
    return block(0, 0, PW, PD, z - T, T) + face(z) + f'<rect width="{PW}" height="{PD}" fill="url(#minor)"/></g>'

def tile(x, y, w, d, z, inner, accent=False):
    o = block(x, y, w, d, z, TILE_H, '#ebedff' if accent else '#fff', 'acc' if accent else 'ink')
    return o + face(z + TILE_H) + f'<g transform="translate({x},{y})">' + inner + '</g></g>'

def num(n, cx, cy):  # flat step circle on a 2D line
    return (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="8" class="acc" style="fill:#fff"/>'
            f'<text x="{cx:.1f}" y="{cy+3:.1f}" class="n">{n}</text>')

def badge(n, x, y):  # step circle lying on a tile top
    return (f'<circle cx="{x}" cy="{y}" r="9" class="acc" style="fill:#fff"/>'
            f'<text x="{x}" y="{y+3.5}" class="n" style="font-size:10.5px">{n}</text>')

def risers(upper_z):
    """Exploded-view alignment lines at the slab corners, from the upper slab down to the plane below."""
    lower_z = upper_z - GAP
    return ''.join(f'<line x1="{iso(x,y,upper_z-T)[0]:.1f}" y1="{iso(x,y,upper_z-T)[1]:.1f}" '
                   f'x2="{iso(x,y,lower_z)[0]:.1f}" y2="{iso(x,y,lower_z)[1]:.1f}" class="dash"/>'
                   for x, y in ((PW, 0), (0, PD)))  # silhouette corners only: the front one crosses tiles

def big_tile_inner(w, icon, title, sub, n, color=INK):
    """Icon centred at the top, title and caption below, step badge in the back corner."""
    style = ' style="font-size:12.5px"' if len(title) > 10 else ''
    return (lu(icon, w / 2 - 20, 22, 40, color) + badge(n, w - 18, 18) +
            f'<text x="{w/2}" y="98" class="h" text-anchor="middle"{style}>{title}</text>'
            f'<text x="{w/2}" y="118" class="s" text-anchor="middle">{sub}</text>')

# --- sheet furniture (flat 2D) -------------------------------------------
H = 1000  # sheet height; a sheet may set bp.H before header() for more room

def header(title):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 {H}" width="1600" height="{H}" font-family="Inter, Helvetica, Arial, sans-serif">
<defs>
<pattern id="minor" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="#ebebed" stroke-width="0.6"/></pattern>
<pattern id="major" width="100" height="100" patternUnits="userSpaceOnUse"><rect width="100" height="100" fill="url(#minor)"/><path d="M100 0H0V100" fill="none" stroke="#d8d8db" stroke-width="0.9"/></pattern>
<marker id="ae" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" orient="auto"><path d="M0 1L10 5L0 9z" fill="{INK}"/></marker>
<clipPath id="sheetclip"><rect width="1600" height="{H}" rx="24"/></clipPath>
</defs>
<style>
.ink{{stroke:{INK};fill:none;stroke-width:1.5;stroke-linejoin:round}}.thin{{stroke:{INK};fill:none;stroke-width:1}}
.acc{{stroke:{ACC};fill:none;stroke-width:2}}.dash{{stroke:{INK};fill:none;stroke-width:1;stroke-dasharray:4 3}}
.t{{fill:{INK};font-size:11px;letter-spacing:1.6px;font-weight:600}}.h{{fill:{INK};font-size:15px;font-weight:700;letter-spacing:.6px}}
.s{{fill:{SOFT};font-size:12px}}.n{{fill:{ACC};font-size:9.5px;font-weight:700;text-anchor:middle}}
</style>
<g clip-path="url(#sheetclip)"><rect width="1600" height="{H}" fill="#ffffff"/><rect width="1600" height="{H}" fill="url(#major)"/>
<rect x="20" y="20" width="1560" height="{H-40}" rx="14" class="ink"/><rect x="30" y="30" width="1540" height="{H-60}" rx="8" class="thin"/>
<text x="60" y="108" fill="{INK}" font-size="36" font-weight="600">{title}</text>
<line x1="60" y1="132" x2="1540" y2="132" class="thin"/>'''

def leader(z, label, cap, icon=None):
    """Layer name on a leader line that ends at the slab's left corner. `icon` is an si()/lu() call at x=330, y=0."""
    X, Y = iso(0, PD, z)
    tx = 354 if icon else 330
    if icon: icon = icon.replace('y="0"', f'y="{Y-24:.0f}"')
    return (f'{icon or ""}<text x="{tx}" y="{Y-9:.0f}" class="h">{label}</text>'
            f'<line x1="330" y1="{Y:.1f}" x2="{X-6:.1f}" y2="{Y:.1f}" class="thin"/>'
            f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="2.5" fill="{INK}"/>'
            f'<text x="330" y="{Y+18:.0f}" class="s">{cap}</text>')

def key(lines, y0=760, x=60):
    o = f'<text x="{x}" y="{y0}" class="t">KEY</text>'
    for i, k in enumerate(lines):
        y = y0 + 26 + i * 22
        o += f'<text x="{x}" y="{y}" fill="{ACC}" font-size="12.5" font-weight="700">{i+1}</text><text x="{x+22}" y="{y}" class="s">{k}</text>'
    return o

def title_block(sheet, view='ISO VIEW', rev='REV A'):
    return (f'<rect x="1380" y="{H-120}" width="160" height="70" class="ink"/><line x1="1380" y1="{H-85}" x2="1540" y2="{H-85}" class="thin"/>'
            f'<line x1="1460" y1="{H-85}" x2="1460" y2="{H-50}" class="thin"/><text x="1392" y="{H-98}" class="t">{sheet}</text>'
            f'<text x="1392" y="{H-62}" class="s">{view}</text><text x="1472" y="{H-62}" class="s">{rev}</text></g></svg>')

# --- writing -------------------------------------------------------------
# One file per sheet, in the light palette only. Dark variants (a `<picture>` swap with `-dark` files) were tried and
# did not switch on the user's GitHub, so the kit does not make them. Rounded corners carry the look on a dark page.

def write_text(path, svg):
    """Write path.svg. `path` has no extension."""
    open(path + '.svg', 'w').write(svg)

def write(name, parts):
    write_text(f'{HERE}/{name}', '\n'.join(parts))

# --- single-plane sheets (CF-02 onwards) ----------------------------------
# Arrow styles: calls a port, implements a port, publishes an event, reads tables.
CALL, IMPL = '', 'stroke-dasharray:9 3 2 3'
EVT, READ = 'stroke-dasharray:6 4', 'stroke-dasharray:1.5 3.5;stroke-linecap:round'

def platform(x0, w, pd):
    """One column's floor: a slab from x0, w wide, pd deep, with the minor grid on top."""
    return block(x0, 0, w, pd, -T, T) + face(0) + f'<rect x="{x0}" width="{w}" height="{pd}" fill="url(#minor)"/></g>'

def card(icon, title, sub, color=INK, lines=(), size=18):
    """Block roof: icon top left, title and caption below, then an optional list. Sizes make up for the plane scale."""
    fill = f'fill:{ACC};' if color == ACC else ''
    o = (lu(icon, 14, 12, 30, color) +
         f'<text x="14" y="64" class="h" style="{fill}font-size:{size}px">{title}</text>'
         f'<text x="14" y="84" class="s" style="font-size:14px">{sub}</text>')
    for i, line in enumerate(lines):
        o += f'<text x="14" y="{112 + i * 19}" class="s" style="fill:{INK};font-size:13px">{line}</text>'
    return o

def chip(icon, title, sub, color=INK, size=14):
    """Roof of a shallow block (about 70 deep): small icon and title on one line, caption below."""
    fill = f'fill:{ACC};' if color == ACC else ''
    return (lu(icon, 12, 11, 22, color) + f'<text x="42" y="29" class="h" style="{fill}font-size:{size}px">{title}</text>'
            f'<text x="12" y="54" class="s" style="font-size:13px">{sub}</text>')

def wire(d, style=CALL, end=True):
    return f'<path d="{d}" class="ink" style="{style}"' + (' marker-end="url(#ae)"/>' if end else '/>')

def legend(items, y0=180, title='RELATIONS', x=60):
    o = f'<text x="{x}" y="{y0}" class="t">{title}</text>'
    for i, (style, label, end) in enumerate(items):
        y = y0 + 28 + i * 26
        o += wire(f'M{x} {y} H{x+44}', style, end) + f'<text x="{x+58}" y="{y+4}" class="s">{label}</text>'
    return o

def floor_labels(items, y=42):
    """Column names on the platform floors: y=42 at the back, or near PD at the front when an arrow uses the back margin.
    Draw after the platforms, before the blocks."""
    return face(0) + ''.join(f'<text x="{x}" y="{y}" class="t" style="font-size:13px">{t}</text>' for x, t in items) + '</g>'
