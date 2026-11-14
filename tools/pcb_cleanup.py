"""Clean up after autorouting and stitching (KiCad Python):
- remove GND vias that overlap copper of another net on either layer;
- remove signal vias that connect on one layer only (router leftovers);
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
pcbnew.SaveBoard(PCB, b)
for r in removed:
    print("removed %s at (%.2f, %.2f)" % r)
