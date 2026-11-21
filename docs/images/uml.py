# 2D UML kit in the blueprint style: actors, use cases, class boxes, ER tables, sequence lifelines and notes.
# Builds on blueprint.py (sheet frame, palette, icons). Rules: ../design-system.md, section "UML sheets".
from blueprint import ACC, INK, SOFT, header, lu, si, title_block, write

MONO = "font-family:'JetBrains Mono','DejaVu Sans Mono',monospace"
TINT = '#ebedff'
HALO = 'paint-order:stroke;stroke:#fff;stroke-width:5px;stroke-linejoin:round'  # keeps labels readable over lines

# Extra markers. Start markers use auto-start-reverse, so one shape serves both ends.
DEFS = f'''<defs>
<marker id="tri" viewBox="0 0 14 14" refX="13" refY="7" markerWidth="14" markerHeight="14" orient="auto-start-reverse"><path d="M1 1L13 7L1 13z" fill="#fff" stroke="{INK}" stroke-width="1.3"/></marker>
<marker id="dia" viewBox="0 0 18 10" refX="17" refY="5" markerWidth="18" markerHeight="10" orient="auto-start-reverse"><path d="M1 5L9 1L17 5L9 9z" fill="{INK}"/></marker>
<marker id="open" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="10" markerHeight="10" orient="auto-start-reverse"><path d="M1 1L9 5L1 9" fill="none" stroke="{INK}" stroke-width="1.4"/></marker>
<marker id="one" viewBox="0 0 14 14" refX="13" refY="7" markerWidth="14" markerHeight="14" orient="auto-start-reverse"><path d="M6 1V13M10 1V13" stroke="{INK}" stroke-width="1.3"/></marker>
<marker id="many" viewBox="0 0 16 16" refX="15" refY="8" markerWidth="16" markerHeight="16" orient="auto-start-reverse"><path d="M15 1L3 8L15 15M3 8H15M1 2V14" fill="none" stroke="{INK}" stroke-width="1.3"/></marker>
</defs>'''

def sheet(title):
    """Sheet frame and title. Close with uml.finish()."""
    return [header(title), DEFS]

def finish(o, name, sheet_id, view='UML'):
    o.append(title_block(sheet_id, view=view))
    write(name, o)

def text(x, y, s, cls='s', anchor='start', style=''):
    return f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}" style="{style}">{s}</text>'

def line(d, kind='solid', start=None, end=None, accent=False):
    """kind: solid | dashed | dotted. start/end: a marker id (ae, tri, dia, open, one, many)."""
    dash = {'solid': '', 'dashed': 'stroke-dasharray:6 4;', 'dotted': 'stroke-dasharray:1.5 3.5;stroke-linecap:round;'}[kind]
    col = f'stroke:{ACC};' if accent else ''
    m = (f' marker-start="url(#{start})"' if start else '') + (f' marker-end="url(#{end})"' if end else '')
    return f'<path d="{d}" class="ink" style="{dash}{col}"{m}/>'

def badge(n, x, y):
    return (f'<circle cx="{x}" cy="{y}" r="9" class="acc" style="fill:#fff"/>'
            f'<text x="{x}" y="{y + 3.5}" class="n" style="font-size:10px">{n}</text>')

def note(x, y, w, lines, accent=False):
    """UML note: a box with a folded corner."""
    h = 16 + 18 * len(lines)
    col = ACC if accent else INK
    o = (f'<path d="M{x} {y} H{x+w-12} L{x+w} {y+12} V{y+h} H{x} Z" style="fill:#f5f6fa;stroke:{col};stroke-width:1.2"/>'
         f'<path d="M{x+w-12} {y} V{y+12} H{x+w}" style="fill:none;stroke:{col};stroke-width:1.2"/>')
    for i, l in enumerate(lines):
        o += text(x + 12, y + 22 + i * 18, l, style='font-size:12px;fill:#0a0b1f')
    return o

def step(n, x, y):
    """Sequence step number: plain bold accent text, right-aligned to x, no circle."""
    return text(x, y, f'{n}', anchor='end', style=f'{HALO};font-size:12px;font-weight:700;fill:{ACC}')

# --- use case diagrams ------------------------------------------------------
def actor(x, y, name, sub='', label_right=False):
    """Stick figure: head centre at (x, y - 40), feet at y. Name under it, or to its right."""
    fig = (f'<circle cx="{x}" cy="{y-48}" r="9" class="ink" style="fill:#fff"/>'
           f'<path d="M{x} {y-39} V{y-16} M{x-16} {y-30} H{x+16} M{x} {y-16} L{x-12} {y} M{x} {y-16} L{x+12} {y}" class="ink"/>')
    if label_right:
        return fig + text(x + 26, y - 30, name, 'h', style='font-size:14px') + text(x + 26, y - 13, sub)
    return fig + text(x, y + 20, name, 'h', 'middle', 'font-size:14px') + text(x, y + 37, sub, anchor='middle')

def usecase(cx, cy, label, rx=105, ry=20):
    return (f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" class="ink" style="fill:#fff"/>'
            + text(cx, cy + 4.5, label, anchor='middle', style='font-size:13px;fill:#0a0b1f'))

def package(x, y, w, h, name):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" class="dash" style="fill:#fff"/>'
            + text(x + 14, y + 22, name, 't', style='font-size:10.5px'))

def system_box(x, y, w, h, name, icon_svg=''):
    """Secondary actor drawn as a box with the «system» stereotype."""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" class="ink" style="fill:#fff"/>' + icon_svg
            + text(x + 44, y + 20, '«system»', style='font-size:10px')
            + text(x + 44, y + 37, name, 'h', style='font-size:13px'))

# --- class diagrams ---------------------------------------------------------
def klass(x, y, w, name, stereo=None, attrs=(), ops=(), accent=False, lh=18):
    """Class box with name, attribute and operation compartments. Returns (svg, (x, y, w, h))."""
    head = 30 + (14 if stereo else 0)
    ha = 10 + len(attrs) * lh if attrs else 10
    ho = 10 + len(ops) * lh if ops else 10
    h = head + ha + ho
    col, fill = (ACC, TINT) if accent else (INK, '#fff')
    o = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" style="fill:{fill};stroke:{col};stroke-width:{2 if accent else 1.5}"/>'
    if stereo:
        o += text(x + w / 2, y + 17, f'«{stereo}»', anchor='middle', style='font-size:10.5px')
    o += text(x + w / 2, y + head - 10, name, 'h', 'middle', f'font-size:14px;{"fill:" + ACC if accent else ""}')
    o += f'<line x1="{x}" y1="{y+head}" x2="{x+w}" y2="{y+head}" style="stroke:{col};stroke-width:1"/>'
    for i, a in enumerate(attrs):
        o += text(x + 10, y + head + 18 + i * lh, a, style=f'{MONO};font-size:11px;fill:#0a0b1f')
    o += f'<line x1="{x}" y1="{y+head+ha}" x2="{x+w}" y2="{y+head+ha}" style="stroke:{col};stroke-width:1"/>'
    for i, op in enumerate(ops):
        o += text(x + 10, y + head + ha + 18 + i * lh, op, style=f'{MONO};font-size:11px;fill:#0a0b1f')
    return o, (x, y, w, h)

# --- ER diagrams ------------------------------------------------------------
def table(x, y, w, name, cols, accent=False, group=''):
    """Database table. cols: (tag, column, type); tag is PK, FK, UQ, PK FK or ''. Returns (svg, box, row_y)."""
    rh, head = 19, 30
    h = head + 8 + len(cols) * rh
    col, fill = (ACC, TINT) if accent else (INK, '#fff')
    o = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" style="fill:#fff;stroke:{col};stroke-width:{2 if accent else 1.5}"/>'
         f'<rect x="{x}" y="{y}" width="{w}" height="{head}" style="fill:{fill};stroke:{col};stroke-width:{2 if accent else 1.5}"/>'
         + text(x + 10, y + 20, name, 'h', style=f'font-size:13.5px;{MONO};{"fill:" + ACC if accent else ""}'))
    if group:
        o += text(x + w - 10, y + 19, group, 't', 'end', 'font-size:9px;letter-spacing:1.2px;fill:#5b6270')
    rows = {}
    for i, (tag, c, t) in enumerate(cols):
        ry = y + head + 8 + i * rh + 12
        rows[c] = ry - 4
        if tag:
            o += text(x + 10, ry, tag, 't', style='font-size:8.5px;letter-spacing:.6px;fill:' + (ACC if 'PK' in tag else SOFT))
        o += text(x + 50, ry, c, style=f'{MONO};font-size:11px;fill:#0a0b1f')
        o += text(x + w - 10, ry, t, anchor='end', style=f'{MONO};font-size:10px')
    return o, (x, y, w, h), rows

# --- sequence diagrams ------------------------------------------------------
class Seq:
    """Participants across the top, lifelines down, messages in order. Call .svg() at the end."""

    def __init__(self, parts, x0=150, x1=1400, top=170, bottom=830, step=36):
        self.o, self.step, self.top, self.bottom = [], step, top, bottom
        gap = (x1 - x0) / (len(parts) - 1)
        self.x = {k: x0 + i * gap for i, (k, *_) in enumerate(parts)}
        self.parts = parts
        self.y = top + 78
        self.n = 0
        self.bw = min(144, gap - 12)  # participant box width

    def head(self):
        o = []
        for k, label, sub, *icon in self.parts:
            x = self.x[k]
            accent = bool(icon and icon[0] == 'accent')
            col, fill = (ACC, TINT) if accent else (INK, '#fff')
            o.append(f'<line x1="{x}" y1="{self.top+46}" x2="{x}" y2="{self.bottom}" class="dash"/>')
            o.append(f'<rect x="{x-self.bw/2}" y="{self.top}" width="{self.bw}" height="46" style="fill:{fill};stroke:{col};stroke-width:1.5"/>')
            o.append(text(x, self.top + 20, label, 'h', 'middle', f'font-size:13px;{"fill:" + ACC if accent else ""}'))
            o.append(text(x, self.top + 37, sub, anchor='middle', style='font-size:10.5px'))
        return o

    def msg(self, a, b, label, kind='call', numbered=True):
        """kind: call (solid, filled head), return (dashed, open head), event (dashed, filled head, accent)."""
        xa, xb, y = self.x[a], self.x[b], self.y
        d = 1 if xb > xa else -1
        style = {'call': ('solid', 'ae', False), 'return': ('dashed', 'open', False), 'event': ('dashed', 'ae', True)}[kind]
        self.o.append(line(f'M{xa + d*6} {y} H{xb - d*6}', style[0], end=style[1], accent=style[2]))
        mid = (xa + xb) / 2
        lx = mid + (12 if numbered else 0)
        self.o.append(text(lx, y - 7, label, anchor='middle', style=f'{MONO};{HALO};font-size:11px;fill:{ACC if kind == "event" else INK}'))
        if numbered:
            self.n += 1
            tw = len(label) * 6.6 / 2
            self.o.append(step(self.n, lx - tw - 8, y - 7))
        self.y += self.step

    def self_call(self, a, label, left=False):
        """A call to itself. left=True draws the loop and label on the left (for the last participant)."""
        x, y, d = self.x[a], self.y, -1 if left else 1
        self.o.append(line(f'M{x + d*6} {y} H{x + d*40} V{y+16} H{x + d*8}', end='ae'))
        self.n += 1
        self.o.append(step(self.n, x + (60 if d > 0 else -46), y + 12))
        self.o.append(text(x + (72 if d > 0 else -78), y + 12, label, anchor='end' if left else 'start',
                           style=f'{MONO};{HALO};font-size:11px;fill:#0a0b1f'))
        self.y += self.step + 10

    def frame(self, kind, guard, y0, y1, a, b):
        """Combined fragment (alt, opt, loop, par) from participant a to b, between y0 and y1."""
        x0, x1 = self.x[a] - 90, self.x[b] + 90
        w = len(kind) * 9 + 20
        self.o.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" style="fill:none;stroke:{INK};stroke-width:1"/>'
                      f'<path d="M{x0} {y0+20} H{x0+w} L{x0+w+8} {y0+12} V{y0}" style="fill:#fff;stroke:{INK};stroke-width:1"/>'
                      + text(x0 + 8, y0 + 15, kind, 't', style='font-size:10px')
                      + text(x0 + w + 16, y0 + 15, f'[{guard}]', style=f'{MONO};font-size:11px'))

    def gap(self, h):
        self.y += h

    def svg(self):
        return self.head() + self.o

# --- flat tables --------------------------------------------------------------
def grid(x, y, widths, head, rows, rh=26, hh=34, size=12, mono_cols=(), tint_rows=(), head_size=11):
    """Flat table. head: labels; rows: lists of cell strings (already escaped). Returns (svg, total height)."""
    xs = [x]
    for w in widths:
        xs.append(xs[-1] + w)
    h = hh + rh * len(rows)
    o = [f'<rect x="{x}" y="{y}" width="{xs[-1]-x}" height="{h}" style="fill:#fff;stroke:{INK};stroke-width:1.5"/>']
    for r in tint_rows:
        o.append(f'<rect x="{x}" y="{y+hh+r*rh}" width="{xs[-1]-x}" height="{rh}" style="fill:{TINT}"/>')
    o.append(f'<line x1="{x}" y1="{y+hh}" x2="{xs[-1]}" y2="{y+hh}" style="stroke:{INK};stroke-width:1.5"/>')
    for i, t in enumerate(head):
        o.append(text(xs[i] + 10, y + hh / 2 + 4, t, 't', style=f'font-size:{head_size}px;letter-spacing:1.2px'))
    for r, cells in enumerate(rows):
        yy = y + hh + r * rh
        if r:
            o.append(f'<line x1="{x}" y1="{yy}" x2="{xs[-1]}" y2="{yy}" style="stroke:#d8d8db;stroke-width:1"/>')
        for c, v in enumerate(cells):
            st = f'font-size:{size}px;fill:{INK}' + (f';{MONO};font-size:{size-1}px' if c in mono_cols else '')
            o.append(text(xs[c] + 10, yy + rh / 2 + 4.5, v, style=st))
    return ''.join(o), h
