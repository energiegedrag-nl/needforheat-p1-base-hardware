"""Check 5: 3D fit of CoreInk + P1-BASE (populated) + tray + lid + RJ12 plugs.
Frame = enclosure frame (x right, y up = towards HAT edge, z up from the CoreInk back).
The CoreInk is a proxy body (40 x 56 x 16 mm, LEGO holes, bus socket 8 mm deep, flush) because the official
model has no socket depth. Needs CadQuery.  Usage: python check_3d_fit.py <repo root>"""
import collections

import os
import sys
import cadquery as cq
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
sys.path.insert(0, os.path.dirname(__file__))
import stepnames
REPO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "..")
GAP, PCB_T = 3.5, 1.6
sys.path.insert(0, os.path.join(REPO, "enclosure"))
import kuip as K   # same parameters as the printed parts
assert K.GAP == GAP

def vol(s):
    p = GProp_GProps(); BRepGProp.VolumeProperties_s(s, p); return p.Mass()
def bbox(s):
    b = Bnd_Box(); BRepBndLib.Add_s(s, b); return b.Get()
def overlap(a, b):
    ba, bb = bbox(a), bbox(b)
    if any(ba[i] > bb[i + 3] + 0.01 or bb[i] > ba[i + 3] + 0.01 for i in range(3)): return 0.0
    c = BRepAlgoAPI_Common(a, b); c.Build()
    return vol(c.Shape()) if c.IsDone() else float("nan")
def dist(a, b):
    d = BRepExtrema_DistShapeShape(a, b); return d.Value() if d.IsDone() else float("nan")

# --- populated board, moved into the enclosure frame -------------------------------
mv = cq.Location(cq.Vector(-100, 100, GAP))
board = collections.defaultdict(list)
for name, shp in stepnames.read(os.path.join(REPO, "enclosure", "p1-base-v3-pcb.step")):
    ref = name.split("/")[0]
    board["PCB" if "_PCB" in name else ref].append(cq.Shape.cast(shp).moved(mv).wrapped)
# --- printed parts ---------------------------------------------------------------
tray = cq.importers.importStep(os.path.join(REPO, "enclosure", "fabrication", "p1-base-kuip.step")).val().wrapped
lid = cq.importers.importStep(os.path.join(REPO, "enclosure", "fabrication", "p1-base-lid.step")).val().wrapped
# --- CoreInk proxy: 40 x 56 x 16 body below z=0 with LEGO holes and the bus socket (8 mm deep, flush) ----
j1 = board["J1"]
jb = Bnd_Box(); [BRepBndLib.Add_s(s, jb) for s in j1]; jx0, jy0, _, jx1, jy1, _ = jb.Get()
jcx, jcy = (jx0 + jx1) / 2, (jy0 + jy1) / 2
core = (cq.Workplane("XY").center(20, -28).rect(40, 56).extrude(-16).edges("|Z").fillet(3))
for (x, y) in K.LEGO_HOLES:
    core = core.cut(cq.Workplane("XY").center(x, -y).circle(4.85 / 2).extrude(-4))
SOCK_D = 8.0
core = core.cut(cq.Workplane("XY").center(jcx, jcy).rect(2 * 2.54 + 0.4, 8 * 2.54 + 0.4).extrude(-SOCK_D))
core = core.val().wrapped
# --- RJ12 plugs, fully inserted, with 30 mm of cable straight out -----------------
def plug(side):
    xs = [s for s in board["J2" if side == "top" else "J3"]]
    b = Bnd_Box(); [BRepBndLib.Add_s(s, b) for s in xs]; x0, y0, z0, x1, y1, z1 = b.Get()
    cx = (x0 + x1) / 2
    zc = GAP + PCB_T + 3.0 + 7.2 / 2          # opening centre in our jack model (VERIFY on the datasheet)
    sgn = 1 if side == "top" else -1
    face = y1 if side == "top" else y0       # front face of the jack
    ins = 8.5                                 # insertion depth
    L = 20.0
    w = cq.Workplane("XZ", origin=(0, 0, 0)).center(cx, zc).rect(9.65, 6.6).extrude(-L * sgn)  # XZ extrudes along -y
    w = w.translate((0, face - sgn * ins, 0))
    latch = cq.Workplane("XZ").center(cx, zc - 3.3 - 1.2).rect(3.6, 2.4).extrude(-12 * sgn).translate((0, face - sgn * ins + sgn * 3, 0))
    cable = cq.Workplane("XZ").center(cx, zc).rect(6.6, 3.2).extrude(-30 * sgn).translate((0, face - sgn * ins + sgn * L, 0))
    return w.union(latch).union(cable).val().wrapped
plugs = {"plug J2 (meter)": plug("top"), "plug J3 (reader)": plug("bottom")}

report = []
def chk(an, a, bn, b, tol=0.001):
    v = overlap(a, b)
    if v > tol: report.append(f"COLLISION {an} x {bn}: {v:.3f} mm3")
    return v
fixed = {"tray": tray, "lid": lid, "CoreInk": core}
mind = []
for ref, shapes in sorted(board.items()):
    for s in shapes:
        for fn, f in fixed.items():
            chk(ref, s, fn, f)
for pn, p in plugs.items():
    for fn, f in list(fixed.items()) + [("PCB", board["PCB"][0])]:
        chk(pn, p, fn, f)
    for ref, shapes in board.items():
        if ref in ("J2", "J3"): continue
        for s in shapes: chk(pn, s, ref, p)
chk("tray", tray, "lid", lid)
chk("tray", tray, "CoreInk", core)
# clearances (closest approach) of parts to the printed parts
for ref, shapes in sorted(board.items()):
    for fn in ("tray", "lid"):
        d = min(dist(s, fixed[fn]) for s in shapes)
        if d < 0.5: mind.append((round(d, 2), ref, fn))
# header pin engagement in the CoreInk socket
pins_z = min(bbox(s)[2] for s in board["J1"])
under = min(bbox(s)[2] for ref, sh in board.items() if ref not in ("J1", "PCB") for s in sh)
lowest = sorted(((round(min(bbox(s)[2] for s in sh), 2), ref) for ref, sh in board.items() if ref not in ("J1", "PCB")))[:4]
print("COLLISIONS:", "\n  ".join([""] + report) if report else "none")
print("closest approach < 0.5 mm (part, printed part):", sorted(mind) or "none")
print(f"J1 header pins end at z = {pins_z:.2f} (CoreInk back = 0): engagement {max(0, -pins_z):.1f} mm of the {SOCK_D} mm socket"
      f" -> pin length below the PCB = {GAP - pins_z:.1f} mm")
print(f"lowest other parts under the PCB (z, ref): {lowest}  (CoreInk back z=0, magnet pads up to z=1.6)")
print("note: the J1 model (tools/gen_3d_models.py) assumes stacking-header pins 9.5 mm below the PCB; the LCSC model of"
      f" C72555 ends 1.4 mm below the PCB, i.e. {GAP - 1.4:.1f} mm above the CoreInk back: it does not reach the socket.")
