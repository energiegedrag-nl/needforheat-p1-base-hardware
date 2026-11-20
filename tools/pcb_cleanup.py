"""Clean up after autorouting and stitching (KiCad Python):
- remove GND vias that overlap copper of another net on either layer;
- remove signal vias that connect on one layer only (router leftovers);
- remove stitching vias (GND vias without tracks) whose drill is closer than the board's
  hole-to-hole minimum to another drill;
- let the GND pours drop islands that have no connection.
Everything is read first (as plain numbers) and removed at the end: after removals KiCad 10's SWIG wrapper can
lose its type information for the board's objects. Zones are not refilled here (that crashes KiCad 10's Python
after removals); refill with
  kicad-cli pcb drc --refill-zones --save-board ...
"""
import math
import os

import pcbnew

PCB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pcb", "needforheat-p1-base-hardware.kicad_pcb")
H2H = pcbnew.FromMM(0.5)  # board setup min_hole_to_hole
CLR = pcbnew.FromMM(0.2)

b = pcbnew.LoadBoard(PCB)
gnd = b.FindNet("GND").GetNetCode()
for z in list(b.Zones()):
    if z.GetNetCode() == gnd:
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)

tracks = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA)]
seg = [(t.GetNetCode(), t.GetLayer(), t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y, t.GetWidth() // 2)
       for t in tracks]
vias = [t for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]
vdat = [(v.GetNetCode(), v.GetPosition().x, v.GetPosition().y, v.GetWidth(pcbnew.F_Cu) // 2, v.GetDrillValue() // 2,
         v.IsLocked(), v.GetNetname()) for v in vias]
pads = [pd for f in b.GetFootprints() for pd in f.Pads()]
holes = [(x, y, d) for _, x, y, _, d, _, _ in vdat]
holes += [(pd.GetPosition().x, pd.GetPosition().y, max(pd.GetDrillSize().x, pd.GetDrillSize().y) // 2)
          for pd in pads if pd.GetDrillSize().x > 0]
ends = {(s[2], s[3]) for s in seg} | {(s[4], s[5]) for s in seg}


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


remove, report, gone = [], [], set()
for i, (net, x, y, r, d, locked, name) in enumerate(vdat):
    why = None
    if net == gnd:
        if any(s[0] != gnd and seg_dist(x, y, s[2], s[3], s[4], s[5]) < r + s[6] + CLR for s in seg):
            why = "GND via on other net"
        elif any(pd.GetNetCode() != gnd and pd.HitTest(pcbnew.VECTOR2I(x, y), r + CLR) for pd in pads):
            why = "GND via on other net"
        elif (x, y) not in ends and not locked:
            for hx, hy, hd in holes:
                if (hx, hy) == (x, y) or (hx, hy) in gone:
                    continue
                if math.hypot(hx - x, hy - y) < d + hd + H2H:
                    why = "stitching via too close to a hole"
                    break
    else:
        layers = {s[1] for s in seg if s[0] == net and ((s[2], s[3]) == (x, y) or (s[4], s[5]) == (x, y))}
        if len(layers) < 2:
            why = f"dangling {name} via"
    if why:
        remove.append(vias[i])
        gone.add((x, y))
        report.append((why, pcbnew.ToMM(x), pcbnew.ToMM(y)))

for v in remove:
    b.Remove(v)
pcbnew.SaveBoard(PCB, b)
for r in report:
    print("removed %s at (%.2f, %.2f)" % r)
print("vias removed:", len(remove))
