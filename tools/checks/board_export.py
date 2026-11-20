"""Export pad positions of the board (KiCad Python):  python board_export.py <board.kicad_pcb> <pads.json>"""
import json, sys
import pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); M = pcbnew.ToMM
out = []
for f in b.GetFootprints():
    for p in f.Pads():
        if not p.GetNumber():
            continue
        out.append(dict(ref=f.GetReference(), pad=p.GetNumber(), x=M(p.GetPosition().x), y=M(p.GetPosition().y),
                        layers=[l for l in ("F.Cu", "B.Cu") if p.IsOnLayer(b.GetLayerID(l))]))
json.dump(out, open(sys.argv[2], "w"))
print(len(out), "pads")
