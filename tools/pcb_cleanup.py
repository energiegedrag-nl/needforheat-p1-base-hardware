"""Clean up after autorouting and stitching (KiCad Python):
- remove GND vias that overlap copper of another net on either layer;
- remove signal vias that connect on one layer only (router leftovers);
- remove stitching vias (GND vias without tracks) whose drill is closer than the board's
  hole-to-hole minimum to another drill;
- let the GND pours drop islands that have no connection.
Zones are not refilled here (that crashes KiCad 10's Python after removals); refill with
  kicad-cli pcb drc --refill-zones --save-board ...
"""
import os
import sys
import pcbnew

PCB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pcb", "needforheat-p1-base-hardware.kicad_pcb")
b = pcbnew.LoadBoard(PCB)
gnd = b.FindNet("GND").GetNetCode()
for z in list(b.Zones()):
    if z.GetNetCode() == gnd:
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
tracks = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA)]
removed = []
for v in [t for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]:
    p, r = v.GetPosition(), v.GetWidth(pcbnew.F_Cu) // 2
    if v.GetNetCode() == gnd:
        clash = [t for t in tracks if t.GetNetCode() != gnd and t.HitTest(p, r + pcbnew.FromMM(0.2))]
        clash += [pd for f in b.GetFootprints() for pd in f.Pads() if pd.GetNetCode() != gnd and pd.HitTest(p, r + pcbnew.FromMM(0.2))]
        if clash:
            removed.append(("GND via on other net", pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)))
            b.Remove(v)
    else:
        layers = {t.GetLayer() for t in tracks if t.GetNetCode() == v.GetNetCode() and (t.GetStart() == p or t.GetEnd() == p)}
        if len(layers) < 2:
            removed.append((f"dangling {v.GetNetname()} via", pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)))
            b.Remove(v)
# hole-to-hole: drop the stitching via of each clashing pair (fanout/router vias carry tracks)
h2h = b.GetDesignSettings().m_HoleToHoleMin
ends = {(t.GetStart().x, t.GetStart().y) for t in tracks} | {(t.GetEnd().x, t.GetEnd().y) for t in tracks}
vias = [t for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]
holes = [(v.GetPosition(), v.GetDrillValue() // 2) for v in vias]
holes += [(pd.GetPosition(), max(pd.GetDrillSize().x, pd.GetDrillSize().y) // 2)
          for f in b.GetFootprints() for pd in f.Pads() if pd.GetDrillSize().x > 0]
gone = set()
for v in vias:
    p = v.GetPosition()
    if v.GetNetCode() != gnd or (p.x, p.y) in ends or v.IsLocked():
        continue
    r = v.GetDrillValue() // 2
    for q, rq in holes:
        if q == p or (q.x, q.y) in gone:
            continue
        if (q - p).EuclideanNorm() < r + rq + h2h:
            removed.append(("stitching via too close to a hole", pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)))
            gone.add((p.x, p.y))
            b.Remove(v)
            break
pcbnew.SaveBoard(PCB, b)
for r in removed:
    print("removed %s at (%.2f, %.2f)" % r)
