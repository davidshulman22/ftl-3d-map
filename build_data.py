#!/usr/bin/env python3
"""Convert raw Overpass JSON (downtown Fort Lauderdale) into data.js for index.html.

Inputs (fetched separately via Overpass API):
  /tmp/ftl_osm.json   buildings, roads, rail, parks, some water
  /tmp/ftl_osm2.json  extra water polygons (North Fork etc.)
  /tmp/ftl_osm3.json  river centerlines
  /tmp/ftl_osm4.json  building:part ways

Output: data.js  (const FTL = {...})
"""
import json, math, sys, os

LAT0, LON0 = 26.1175, -80.123
MX = 111320 * math.cos(math.radians(LAT0))
MZ = 110574
CLIP_X, CLIP_Z = 2790, 1930

def proj(lat, lon):
    return ((lon - LON0) * MX, -(lat - LAT0) * MZ)

def load(p):
    with open(p) as f:
        return json.load(f)['elements']

def ring_pts(geom):
    pts = [(p['lat'], p['lon']) for p in geom]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts

def shoelace(pts):
    s = 0
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        s += a[1] * b[0] - b[1] * a[0]
    return s / 2

def ensure_ccw(pts):
    return pts if shoelace(pts) > 0 else pts[::-1]

def project_ring(pts):
    out = []
    for la, lo in pts:
        x, z = proj(la, lo)
        xi, zi = round(x), round(z)
        if not out or out[-1] != [xi, zi]:
            out.append([xi, zi])
    return out

def clip_ring(ring):
    def clip_edge(pts, inside, intersect):
        out = []
        n = len(pts)
        for i in range(n):
            cur, prv = pts[i], pts[i - 1]
            ci, pi = inside(cur), inside(prv)
            if ci:
                if not pi:
                    out.append(intersect(prv, cur))
                out.append(cur)
            elif pi:
                out.append(intersect(prv, cur))
        return out
    def ix_x(v):
        def f(a, b):
            t = (v - a[0]) / (b[0] - a[0])
            return [v, a[1] + t * (b[1] - a[1])]
        return f
    def ix_z(v):
        def f(a, b):
            t = (v - a[1]) / (b[1] - a[1])
            return [a[0] + t * (b[0] - a[0]), v]
        return f
    r = ring
    r = clip_edge(r, lambda p: p[0] >= -CLIP_X, ix_x(-CLIP_X))
    if not r: return []
    r = clip_edge(r, lambda p: p[0] <= CLIP_X, ix_x(CLIP_X))
    if not r: return []
    r = clip_edge(r, lambda p: p[1] >= -CLIP_Z, ix_z(-CLIP_Z))
    if not r: return []
    r = clip_edge(r, lambda p: p[1] <= CLIP_Z, ix_z(CLIP_Z))
    return [[round(p[0]), round(p[1])] for p in r]

def parse_h(t):
    h = t.get('height')
    if h:
        try:
            s = str(h).lower().replace('m', '').strip()
            if 'ft' in s or "'" in s:
                return float(s.replace('ft', '').replace("'", '').strip()) * 0.3048
            return float(s)
        except ValueError:
            pass
    lv = t.get('building:levels')
    if lv:
        try:
            return float(lv) * 3.3 + 1.5
        except ValueError:
            pass
    return None

def stitch(members, roles=('outer',)):
    segs = [ring_pts(m['geometry']) for m in members
            if m.get('type') == 'way' and m.get('geometry') and m.get('role', 'outer') in roles]
    segs = [s for s in segs if len(s) >= 2]
    rings = []
    while segs:
        cur = segs.pop(0)
        changed = True
        while changed and cur[0] != cur[-1]:
            changed = False
            for i, s in enumerate(segs):
                if s[0] == cur[-1]:
                    cur += s[1:]; segs.pop(i); changed = True; break
                if s[-1] == cur[-1]:
                    cur += s[::-1][1:]; segs.pop(i); changed = True; break
        if len(cur) >= 3:
            rings.append(cur)
    return rings

def centroid(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))

def pt_in(la, lo, pts):
    inside = False
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        if (a[1] > lo) != (b[1] > lo):
            t = (lo - a[1]) / (b[1] - a[1])
            if a[0] + t * (b[0] - a[0]) > la:
                inside = not inside
    return inside

main = load('/tmp/ftl_osm.json')
extra_water = load('/tmp/ftl_osm2.json')
rivers = load('/tmp/ftl_osm3.json')
parts_raw = load('/tmp/ftl_osm4.json')

# aerial imagery (USGS NAIP, public domain): ground.jpg covers this bbox
IMG_LON = (-80.151, -80.095)
IMG_LAT = (26.100, 26.135)
IMG_HX = round((IMG_LON[1] - LON0) * MX)
IMG_HZ = round((LAT0 - IMG_LAT[0]) * MZ)
try:
    from PIL import Image
    _img = Image.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ground.jpg')).convert('RGB')
    _IW, _IH = _img.size
except Exception:
    _img = None

def roof_color(ring):
    if _img is None:
        return None
    cx = sum(p[0] for p in ring) / len(ring)
    cz = sum(p[1] for p in ring) / len(ring)
    pts = [(cx, cz)]
    for p in ring[:8]:
        pts.append(((p[0] + cx) / 2, (p[1] + cz) / 2))
    rs = gs = bs = n = 0
    for x, z in pts:
        u = (x + IMG_HX) / (2 * IMG_HX) * _IW
        v = (z + IMG_HZ) / (2 * IMG_HZ) * _IH
        if 0 <= u < _IW and 0 <= v < _IH:
            r, g, b = _img.getpixel((int(u), int(v)))
            rs += r; gs += g; bs += b; n += 1
    if not n:
        return None
    r0, g0, b0 = rs / n, gs / n, bs / n
    lum = 0.299 * r0 + 0.587 * g0 + 0.114 * b0
    def cl(c):
        return max(58, min(240, int(lum + (c - lum) * 1.45 + 6)))
    return (cl(r0) << 16) | (cl(g0) << 8) | cl(b0)

H_PATCH = {
    273273699: 88,    # Bank of America Plaza
    1066256701: 80,   # Broward County Judicial Complex tower
    551457871: 12,    # Brightline station
    532105760: 14,    # NSU Art Museum
    611265319: 22,    # Riverside Hotel
    611265303: 92,    # Amaray Las Olas
    555791492: 42,    # New River Center
    611211804: 30,    # 300 SE 2nd St (Ginsberg Shulman)
    833916696: 28,    # 10X Las Olas Walk
    611595699: 26,    # Camden Las Olas
    317348333: 26,    # Main Library
    521118084: 22,    # Arts & Science garage
}
H_PATCH_NAME = {
    'broward financial center': 87,
    'museum of discovery and science': 18,
}
CARDS = [
    {'id': 659546362, 'n': '100 Las Olas', 'f': '499 ft · 46 floors · 2020',
     'o': 'Tallest building in Fort Lauderdale — condos above the Hyatt Centric hotel.'},
    {'id': 1396083767, 'n': 'Veneto Las Olas', 'f': '~499 ft · 45 floors',
     'o': 'One of the newest towers on the Las Olas skyline.'},
    {'id': 273260385, 'n': 'Las Olas Grand', 'f': '~380 ft · 38 floors · 2005',
     'o': 'Condo tower on the New River, next to the Riverwalk.'},
    {'name': 'las olas river house', 'n': 'Las Olas River House', 'f': '~453 ft · 42 floors · 2004',
     'o': 'Condo tower rising straight off the Riverwalk.'},
    {'id': 273267634, 'n': '110 Tower', 'f': '~410 ft · 30 floors · 1988',
     'o': 'Office tower next door to the courthouse — heavy lawyer traffic.', 'k': 2},
    {'id': 274506959, 'n': 'One Financial Plaza', 'f': '376 ft · 28 floors · 1972',
     'o': 'The dark tower that reigned as the city’s tallest for decades.', 'k': 4},
    {'id': 273273699, 'n': 'Bank of America Plaza', 'f': '~290 ft · 23 floors · 2002',
     'o': 'Office anchor of the Las Olas City Centre block.', 'k': 2},
    {'name': 'broward financial center', 'n': 'Broward Financial Centre', 'f': '286 ft · 24 floors · 1985',
     'o': 'Granite office tower on East Broward Boulevard.', 'k': 4},
    {'id': 1066256701, 'n': 'Broward County Courthouse', 'f': '20 floors · opened 2017',
     'o': 'Broward County Judicial Complex — where the probate division sits.', 'k': 1},
    {'id': 551457871, 'n': 'Brightline Fort Lauderdale', 'f': 'opened 2018',
     'o': 'Trains to Miami, West Palm Beach, and Orlando.', 'k': 1},
    {'id': -7540489, 'n': 'Museum of Discovery & Science', 'f': 'opened 1992',
     'o': 'MODS and the AutoNation IMAX theater.', 'k': 1},
    {'id': 532105760, 'n': 'NSU Art Museum', 'f': 'building opened 1986',
     'o': 'Modern and contemporary art at Las Olas and Andrews.', 'k': 1},
    {'id': 611265319, 'n': 'Riverside Hotel', 'f': 'opened 1936',
     'o': 'The grande dame of Las Olas Boulevard.', 'k': 1},
    {'id': 611265303, 'n': 'Amaray Las Olas', 'f': '~30 floors · 2017',
     'o': 'Luxury rental tower in the Flagler Village direction.'},
    {'id': 555791492, 'n': 'New River Center', 'f': '10 floors · 1990',
     'o': 'Office block on Las Olas — longtime home of the Sun-Sentinel.', 'k': 2},
    {'id': 611211804, 'n': 'Ginsberg Shulman, PL', 'f': '300 SE 2nd St · Suite 600',
     'o': 'Probate, estate planning, and trust administration — home base.', 'k': 1},
]
RESI = {'apartments', 'residential', 'condominium', 'dormitory', 'hotel'}
HOUSE = {'house', 'detached', 'garage', 'garages', 'shed', 'bungalow', 'carport', 'terrace', 'static_caravan', 'roof'}

buildings = []   # (id, rings(latlon), tags)
for e in main:
    t = e.get('tags', {})
    if not t.get('building'):
        continue
    if e['type'] == 'way' and e.get('geometry'):
        pts = ring_pts(e['geometry'])
        if len(pts) >= 3:
            buildings.append((e['id'], [pts], t))
    elif e['type'] == 'relation':
        outers = stitch(e.get('members', []))
        if outers:
            buildings.append((-e['id'], outers, t))

parts = []
for e in parts_raw:
    t = e.get('tags', {})
    if e['type'] != 'way' or not e.get('geometry'):
        continue
    pts = ring_pts(e['geometry'])
    if len(pts) < 3:
        continue
    h = parse_h(t)
    mh = 0.0
    if t.get('min_height'):
        try: mh = float(str(t['min_height']).replace('m', '').strip())
        except ValueError: pass
    elif t.get('building:min_level'):
        try: mh = float(t['building:min_level']) * 3.3
        except ValueError: pass
    parts.append((e['id'], pts, h or 6.0, mh, t))

# suppress outlines that have parts inside them
suppressed = {}
for bid, rings, t in buildings:
    for pid, ppts, ph, pmh, pt in parts:
        cla, clo = centroid(ppts)
        if pt_in(cla, clo, rings[0]):
            suppressed.setdefault(bid, []).append(pid)

card_by_id = {}
card_by_name = {}
out_cards = []
for c in CARDS:
    idx = len(out_cards)
    out_cards.append({'n': c['n'], 'f': c['f'], 'o': c['o']})
    if 'id' in c:
        card_by_id[c['id']] = (idx, c.get('k'))
    if 'name' in c:
        card_by_name[c['name']] = (idx, c.get('k'))

def kind_for(t, h):
    b = t.get('building', 'yes')
    if b in HOUSE or h <= 5.5:
        return 0
    if b in RESI:
        return 3 if h > 28 else 1
    if h >= 50:
        return 2
    if h >= 13:
        return 1
    return 0

def default_h(t, area_m2, bid, cx=0):
    b = t.get('building', 'yes')
    if b in HOUSE:
        return 4.5
    if cx > 1750 and area_m2 > 700:
        return 40.0 + (abs(bid) % 6) * 12.0
    if b in RESI:
        return 9.0
    if b == 'church':
        return 10.0
    if area_m2 > 1200:
        return 12.0 + (abs(bid) % 5) * 2.5
    return 6.0

def ring_area(pr):
    s = 0
    for i in range(len(pr)):
        a, b = pr[i], pr[(i + 1) % len(pr)]
        s += a[0] * b[1] - b[0] * a[1]
    return abs(s) / 2

out_b = []        # merged: [kind, h, minh, ring...]
out_int = []      # interactive: {c:cardIdx, k:kind, m:[[h,minh,ring],...]}
int_groups = {}

def emit(bid, rings, t, h, mh, card):
    pr = [project_ring(r) for r in rings]
    pr = [r for r in pr if len(r) >= 3 and ring_area(r) >= 4]
    if not pr:
        return
    if card is not None:
        idx, kov = card
        k = kov if kov is not None else kind_for(t, h)
        g = int_groups.setdefault(idx, {'c': idx, 'k': k, 'm': []})
        for r in pr:
            g['m'].append([round(h, 1), round(mh, 1), r, roof_color(r) or 11250603])
    else:
        k = kind_for(t, h)
        for r in pr:
            out_b.append([k, round(h, 1), round(mh, 1), r, roof_color(r) or 11250603])

part_by_id = {p[0]: p for p in parts}
emitted_parts = set()
for bid, rings, t in buildings:
    name = (t.get('name') or '').lower()
    card = card_by_id.get(bid) or (card_by_name.get(name) if name else None)
    h = parse_h(t)
    if bid in H_PATCH and (h is None or H_PATCH[bid] > (h or 0)):
        h = H_PATCH[bid]
    for k2, v in H_PATCH_NAME.items():
        if k2 == name and (h is None or v > h):
            h = v
    if bid in suppressed:
        for pid in suppressed[bid]:
            if pid in emitted_parts:
                continue
            emitted_parts.add(pid)
            pid_, ppts, ph, pmh, ptags = part_by_id[pid]
            emit(pid, [ppts], ptags, ph, pmh, card)
        continue
    if h is None:
        pr0 = project_ring(rings[0])
        ar = ring_area(pr0)
        cx0 = sum(p[0] for p in pr0) / len(pr0) if pr0 else 0
        h = default_h(t, ar, bid, cx0)
    emit(bid, rings, t, h, 0.0, card)

for idx, g in sorted(int_groups.items()):
    out_int.append(g)

# roads
WIDTHS = {'motorway': 18, 'motorway_link': 10, 'trunk': 16, 'trunk_link': 10,
          'primary': 14, 'secondary': 12, 'tertiary': 10, 'residential': 7,
          'unclassified': 7, 'living_street': 6, 'pedestrian': 4}
out_roads = []
road_ways = []
for e in main:
    t = e.get('tags', {})
    hw = t.get('highway')
    if not hw or e['type'] != 'way' or not e.get('geometry'):
        continue
    w = WIDTHS.get(hw)
    if not w:
        continue
    pts = [list(proj(p['lat'], p['lon'])) for p in e['geometry']]
    pts = [[round(x), round(z)] for x, z in pts]
    pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
    if len(pts) < 2:
        continue
    out_roads.append([w] + [c for p in pts for c in p])
    L = sum(math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1]) for i in range(len(pts)-1))
    road_ways.append((L, w, pts, t.get('name') or ''))

routes = [pts for L, w, pts, n in sorted(road_ways, key=lambda r: -r[0])[:20] if w >= 7]

# Las Olas chain for palms
lo_segs = [pts for L, w, pts, n in road_ways if n == 'East Las Olas Boulevard']
lo_chain = []
if lo_segs:
    segs = [s[:] for s in lo_segs]
    cur = segs.pop(0)
    changed = True
    while changed:
        changed = False
        for i, s in enumerate(segs):
            if s[0] == cur[-1]: cur += s[1:]; segs.pop(i); changed = True; break
            if s[-1] == cur[-1]: cur += s[::-1][1:]; segs.pop(i); changed = True; break
            if s[-1] == cur[0]: cur = s[:-1] + cur; segs.pop(i); changed = True; break
            if s[0] == cur[0]: cur = s[::-1][:-1] + cur; segs.pop(i); changed = True; break
    lo_chain = cur

# rail
out_rail = []
for e in main:
    t = e.get('tags', {})
    if t.get('railway') == 'rail' and e['type'] == 'way' and e.get('geometry'):
        pts = [list(proj(p['lat'], p['lon'])) for p in e['geometry']]
        out_rail.append([c for p in pts for c in [round(p[0]), round(p[1])]])

# parks
out_parks = []
for e in main:
    t = e.get('tags', {})
    if t.get('leisure') in ('park', 'garden'):
        if e['type'] == 'way' and e.get('geometry'):
            rs = [ring_pts(e['geometry'])]
        elif e['type'] == 'relation':
            rs = stitch(e.get('members', []))
        else:
            continue
        for r in rs:
            cr = clip_ring(ensure_ccw(project_ring(r)))
            if len(cr) >= 3:
                out_parks.append(cr)

# water polygons
out_water = []
seen_w = set()
for e in list(extra_water) + list(main):
    t = e.get('tags', {})
    if t.get('natural') != 'water' and t.get('waterway') != 'riverbank':
        continue
    key = (e['type'], e['id'])
    if key in seen_w:
        continue
    seen_w.add(key)
    if e['type'] == 'way' and e.get('geometry'):
        rs = [ring_pts(e['geometry'])]
    elif e['type'] == 'relation':
        rs = stitch(e.get('members', []))
    else:
        continue
    for r in rs:
        cr = clip_ring(ensure_ccw(project_ring(r)))
        if len(cr) >= 3:
            out_water.append(cr)

# river centerline: main stem + east continuation, orientation-robust stitch
rv_ways = {e['id']: e for e in rivers if e.get('tags', {}).get('waterway') == 'river'}
def gap(p, q):
    return math.hypot(p[-1][0] - q[0][0], p[-1][1] - q[0][1])
rv = []
if 160701747 in rv_ways and 161854747 in rv_ways:
    a = [(p['lat'], p['lon']) for p in rv_ways[160701747]['geometry']]
    b = [(p['lat'], p['lon']) for p in rv_ways[161854747]['geometry']]
    combos = [(a, b), (a, b[::-1]), (a[::-1], b), (a[::-1], b[::-1])]
    best = min(combos, key=lambda c: gap(c[0], c[1]))
    rv = best[0] + best[1]
    if rv[0][1] > rv[-1][1]:
        rv = rv[::-1]
elif 160701747 in rv_ways:
    rv = [(p['lat'], p['lon']) for p in rv_ways[160701747]['geometry']]
rv_p = []
for la, lo in rv:
    x, z = proj(la, lo)
    if abs(x) < 3150 and abs(z) < 2200:
        rv_p.append([round(x), round(z)])

# labels: name, x, topY, z
LABELED = {'100 Las Olas', 'Broward County Courthouse', 'Ginsberg Shulman, PL',
           'Brightline Fort Lauderdale', 'Museum of Discovery & Science', 'Riverside Hotel', 'Veneto Las Olas'}
out_labels = []
for g in out_int:
    c = out_cards[g['c']]
    if c['n'] in LABELED and g['m']:
        tallest = max(g['m'], key=lambda m: m[0])
        ring = tallest[2]
        cx = sum(p[0] for p in ring) / len(ring)
        cz = sum(p[1] for p in ring) / len(ring)
        out_labels.append([c['n'], round(cx), round(tallest[0] + 8), round(cz)])

data = {'b': out_b, 'i': out_int, 'cards': out_cards, 'r': out_roads, 'rl': out_rail,
        'pk': out_parks, 'w': out_water, 'rv': rv_p, 'routes': routes, 'lo': lo_chain,
        'lbl': out_labels, 'ext': [CLIP_X, CLIP_Z], 'img': [IMG_HX, IMG_HZ]}
js = 'const FTL=' + json.dumps(data, separators=(',', ':')) + ';'
out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.js')
with open(out_path, 'w') as f:
    f.write(js)
print('buildings merged:', len(out_b), ' interactive groups:', len(out_int),
      ' roads:', len(out_roads), ' water polys:', len(out_water), ' parks:', len(out_parks),
      ' rail:', len(out_rail), ' river pts:', len(rv_p), ' routes:', len(routes),
      ' las olas pts:', len(lo_chain), ' labels:', len(out_labels))
print('data.js size: %.0f KB' % (os.path.getsize(out_path) / 1024))
