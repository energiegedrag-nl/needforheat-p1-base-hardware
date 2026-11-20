"""Check 4: rebuild connectivity from the gerber + drill files only (geometry; the KiCad net attributes in
the files are ignored), then compare with the schematic netlist (kicad-cli export).
Needs: pip install gerbonara shapely
Usage: python check_gerber_netlist.py <gerber dir> <pads.json> <sch.net>"""
import glob, json, math, os, sys, collections
from gerbonara import GerberFile, ExcellonFile
from gerbonara.utils import MM
from gerbonara import graphic_primitives as gp
from shapely.geometry import Point, LineString, Polygon, box
from shapely import affinity, ops
gdir, padsf, netf = sys.argv[1:4]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tools/sexpr.py
from sexpr import parse, find, first

def arcpts(x1, y1, x2, y2, cx, cy, cw, n=24):
    a1, a2 = math.atan2(y1 - cy, x1 - cx), math.atan2(y2 - cy, x2 - cx)
    r = math.hypot(x1 - cx, y1 - cy)
    if cw:
        while a2 >= a1: a2 -= 2 * math.pi
    else:
        while a2 <= a1: a2 += 2 * math.pi
    if abs(x1 - x2) < 1e-9 and abs(y1 - y2) < 1e-9: a2 = a1 + (-2 * math.pi if cw else 2 * math.pi)
    return [(cx + r * math.cos(a1 + (a2 - a1) * i / n), cy + r * math.sin(a1 + (a2 - a1) * i / n)) for i in range(n + 1)]

def prim_geom(p):
    if isinstance(p, gp.Circle): return Point(p.x, p.y).buffer(p.r, 32)
    if isinstance(p, gp.Line): return LineString([(p.x1, p.y1), (p.x2, p.y2)]).buffer(p.width / 2, 16)
    if isinstance(p, gp.Arc):
        return LineString(arcpts(p.x1, p.y1, p.x2, p.y2, p.cx, p.cy, p.clockwise)).buffer(p.width / 2, 16)
    if isinstance(p, gp.Rectangle):
        return affinity.rotate(box(p.x - p.w / 2, p.y - p.h / 2, p.x + p.w / 2, p.y + p.h / 2), p.rotation, origin=(p.x, p.y), use_radians=True)
    if isinstance(p, gp.ArcPoly):
        pts = []
        outline = list(p.outline)
        for i, (x, y) in enumerate(outline):
            nx, ny = outline[(i + 1) % len(outline)]
            arc = p.arc_centers[i] if p.arc_centers and i < len(p.arc_centers) else None
            if arc:
                cw, (cx, cy) = arc
                pts += arcpts(x, y, nx, ny, cx, cy, cw)[:-1]
            else:
                pts.append((x, y))
        g = Polygon(pts) if len(pts) >= 3 else Polygon()
        return g if g.is_valid else g.buffer(0)
    raise TypeError(type(p))

def layer_geom(path):
    g = GerberFile.open(path)
    acc = Polygon()
    n = 0
    for obj in g.objects:
        for p in obj.to_primitives(unit=MM):
            geo = prim_geom(p)
            acc = acc.union(geo) if p.polarity_dark else acc.difference(geo)
            n += 1
    return acc, n

fcu, nf = layer_geom(glob.glob(os.path.join(gdir, "*F_Cu.g*"))[0])
bcu, nb = layer_geom(glob.glob(os.path.join(gdir, "*B_Cu.g*"))[0])
pth = ExcellonFile.open(glob.glob(os.path.join(gdir, "*-PTH.drl"))[0])
holes = []
for obj in pth.objects:
    for p in obj.to_primitives(unit=MM):
        if isinstance(p, gp.Circle): holes.append((p.x, p.y, p.r))
        elif isinstance(p, gp.Line): holes.append(((p.x1 + p.x2) / 2, (p.y1 + p.y2) / 2, p.width / 2))
polys = {"F": list(getattr(fcu, "geoms", [fcu])), "B": list(getattr(bcu, "geoms", [bcu]))}
print(f"gerber primitives F {nf}, B {nb}; copper islands F {len(polys['F'])}, B {len(polys['B'])}; plated holes {len(holes)}")
# union-find over islands
parent = {}
def find_(a):
    while parent.setdefault(a, a) != a: a = parent[a]
    return a
def union(a, b): parent[find_(a)] = find_(b)
def island(layer, x, y):
    pt = Point(x, y)
    for i, g in enumerate(polys[layer]):
        if g.contains(pt): return (layer, i)
    return None
for x, y, r in holes:
    # a plated hole connects whatever copper surrounds it on both layers (ring around the hole)
    ring = Point(x, y).buffer(r + 0.05).exterior
    ids = [(l, i) for l in "FB" for i, g in enumerate(polys[l]) if g.intersects(ring)]
    for a in ids[1:]: union(ids[0], a)
    for a in ids: find_(a)
pads = json.load(open(padsf))
padnode, unplaced = {}, []
for p in pads:
    x, y = p["x"], -p["y"]
    ids = [island(l[0], x, y) for l in p["layers"]]
    ids = [i for i in ids if i]
    if not ids: unplaced.append(f"{p['ref']}.{p['pad']}"); continue
    for a in ids[1:]: union(ids[0], a)
    padnode[(p["ref"], p["pad"])] = ids[0]
derived = collections.defaultdict(set)
for k, n in padnode.items(): derived[find_(n)].add(k)
# schematic netlist
net = parse(open(netf, encoding="utf8").read())
schnet = {}
for n in find(first(net, "nets"), "net"):
    name = first(n, "name")[1]
    for node in find(n, "node"):
        schnet[(first(node, "ref")[1], first(node, "pin")[1])] = name
opens, shorts = [], []
by_sch = collections.defaultdict(set)
for k, n in padnode.items():
    if k in schnet: by_sch[schnet[k]].add(find_(n))
for name, isl in by_sch.items():
    if len(isl) > 1 and not name.startswith("unconnected"):
        opens.append(f"{name}: split over {len(isl)} copper islands: " + " | ".join(
            ",".join(sorted(f"{r}.{p}" for r, p in derived[i] if schnet.get((r, p)) == name)) for i in isl))
for i, members in derived.items():
    names = {schnet.get(m, "<no net>") for m in members}
    if len(names) > 1:
        shorts.append(f"island with {len(members)} pads joins: {sorted(names)}")
print("pads not on any copper:", unplaced or "none")
print("pads in board but not in schematic netlist:", sorted(f"{r}.{p}" for r, p in padnode if (r, p) not in schnet) or "none")
print(f"schematic nets checked: {len(by_sch)}; derived copper nets: {len(derived)}")
print("OPENS:", "\n  ".join([""] + opens) if opens else "none")
print("SHORTS:", "\n  ".join([""] + shorts) if shorts else "none")
