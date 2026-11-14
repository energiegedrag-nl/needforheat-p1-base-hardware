"""Build the P1-BASE v3 board from the schematic netlist, then autoroute it.

Run with KiCad's own Python (it needs the pcbnew module):
  "<KiCad>/bin/python.exe" tools/gen_pcb.py [--no-route]

Steps: export the netlist with kicad-cli, create the board outline and
footprints, place every part (fixed positions for connectors, packed blocks
for the rest), assign nets, add ground pours, then route with Freerouting
(Specctra DSN/SES round trip) and run DRC.

Coordinate frame: the top left corner of the CoreInk (seen from its back,
HAT edge up) is at (X0, Y0); the board is 40 x 56 mm like the CoreInk.
"""
import math
import os
import re
import subprocess
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import parse, find, first  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCBDIR = os.path.join(ROOT, "pcb")
NAME = "needforheat-p1-base-hardware"
KICAD = os.path.dirname(os.path.dirname(sys.executable))
CLI = os.path.join(KICAD, "bin", "kicad-cli.exe")
FPDIR = os.path.join(KICAD, "share", "kicad", "footprints")
JAVA = os.environ.get("JAVA", os.path.expandvars(r"%LOCALAPPDATA%\freerouting\jre25\jdk-25.0.5+8-jre\bin\java.exe"))
FREEROUTING = os.environ.get("FREEROUTING", os.path.expandvars(r"%LOCALAPPDATA%\freerouting\freerouting.jar"))

X0, Y0 = 100.0, 100.0
W, H = 40.0, 56.0
MM = pcbnew.FromMM


def P(x, y):
    """Board position from CoreInk-relative mm."""
    return pcbnew.VECTOR2I(MM(X0 + x), MM(Y0 + y))


# Fixed placements (CoreInk-relative mm, rotation in degrees)
FIXED = {
    # meter jack at the top edge, opening up; existing-reader jack at the bottom edge, opening down
    "J2": (15.5 - 2.55, 10.89 + 0.3, 180),
    "J3": (15.5 + 2.55, 56.0 - 10.89 - 0.3, 0),
    # CoreInk MI-BUS: centre 6.03 mm from the right edge, 36.87 mm from the top edge
    "J1": (40.0 - 6.03, 36.87, 0),
}
# kuip pegs (NPTH) at three of the four LEGO-hole axes: also keys the PCB in the enclosure
PEGS = [(4.0, 4.0), (36.0, 4.0), (4.0, 52.0)]
# Blocks for the SMD parts: rectangle (x1, y1, x2, y2) and the parts, packed in rows
BLOCKS = [
    ((21.5, 0.8, 39.2, 16.0), ["Q1", "R1", "D1", "C1", "C2", "D2", "C3", "R21", "R22", "C6", "TP1", "TP2"]),
    ((0.8, 13.6, 31.0, 27.0), ["D5", "R8", "R9", "Q3", "R10", "Q4", "R11", "R12", "Q5", "R13", "R14", "R15", "D7",
                               "R20", "LED2", "TP4", "D6", "R16", "R18", "R19"]),
    ((0.8, 27.0, 20.8, 42.0), ["D3", "R2", "R3", "U1", "C4", "R4", "R32", "Q2", "R5", "R6", "D4", "R7", "LED1"]),
    ((20.0, 24.0, 31.0, 55.4), ["Q6", "R23", "C7", "R24", "Q7", "R25", "R26", "C8", "U3", "R27", "R28", "Q8",
                                "R29", "R30", "C9", "R31", "LED3"]),
    ((0.8, 38.0, 8.0, 49.0), ["TP3", "TP5", "TP6", "TP7"]),
]


def netlist():
    sch = os.path.join(PCBDIR, NAME + ".kicad_sch")
    out = os.path.join(PCBDIR, NAME + ".net")
    subprocess.run([CLI, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", out, sch], check=True)
    with open(out, encoding="utf8") as f:
        n = parse(f.read())
    os.remove(out)
    comps = {}
    for c in find(first(n, "components"), "comp"):
        ref = first(c, "ref")[1]
        fields = {}
        fl = first(c, "fields")
        if fl:
            for fd in find(fl, "field"):
                nm = first(fd, "name")[1]
                fields[nm] = fd[2] if len(fd) > 2 and not isinstance(fd[2], list) else ""
        props = {first(p, "name")[1]: (first(p, "value") or [None, ""])[1] for p in find(c, "property")}
        comps[ref] = dict(value=first(c, "value")[1], fp=first(c, "footprint")[1], fields=fields, props=props)
    nets = {}
    for nt in find(first(n, "nets"), "net"):
        name = first(nt, "name")[1]
        for node in find(nt, "node"):
            nets.setdefault(name, []).append((first(node, "ref")[1], first(node, "pin")[1]))
    return comps, nets


def load_fp(libid):
    lib, name = libid.split(":", 1)
    path = os.path.join(PCBDIR, lib + ".pretty") if lib == "p1base" else os.path.join(FPDIR, lib + ".pretty")
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise SystemExit("footprint not found: " + libid)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def add_outline(b):
    r = 3.0
    pts = [(r, 0), (W - r, 0), (W, r), (W, H - r), (W - r, H), (r, H), (0, H - r), (0, r)]
    segs = [(pts[0], pts[1]), (pts[2], pts[3]), (pts[4], pts[5]), (pts[6], pts[7])]
    for a, c in segs:
        s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a)); s.SetEnd(P(*c)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); b.Add(s)
    k = r * (1 - 0.5 ** 0.5)  # offset of the arc midpoint from the corner
    corners = [((0, r), (k, k), (r, 0)), ((W - r, 0), (W - k, k), (W, r)),
               ((W, H - r), (W - k, H - k), (W - r, H)), ((r, H), (k, H - k), (0, H - r))]
    for s, m, e in corners:
        a = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_ARC)
        a.SetArcGeometry(P(*s), P(*m), P(*e))
        a.SetLayer(pcbnew.Edge_Cuts); a.SetWidth(MM(0.1)); b.Add(a)


def courtyard(fp):
    bb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox() if fp.GetCourtyard(pcbnew.F_CrtYd).OutlineCount() else fp.GetBoundingBox(False)
    return pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight()), bb


def rel_box(fp):
    _, _, bb = courtyard(fp)
    return (pcbnew.ToMM(bb.GetLeft()) - X0, pcbnew.ToMM(bb.GetTop()) - Y0,
            pcbnew.ToMM(bb.GetRight()) - X0, pcbnew.ToMM(bb.GetBottom()) - Y0)


def _hit(a, b, gap):
    return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1])


def place_block(fps, rect, refs, obstacles, gap=0.3, step=0.25):
    """Raster-scan placement: each part goes to the first free spot in the block."""
    x1, y1, x2, y2 = rect
    for ref in refs:
        fp = fps[ref]
        fp.SetOrientationDegrees(0)
        fp.SetPosition(P(0, 0))
        w, h, bb = courtyard(fp)
        ox, oy = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
        spot = None
        y = y1
        while spot is None and y + h <= y2 + 1e-6:
            x = x1
            while x + w <= x2 + 1e-6:
                box = (x, y, x + w, y + h)
                if not any(_hit(box, o, gap) for o in obstacles):
                    spot = box
                    break
                x += step
            y += step
        if spot is None:
            raise SystemExit(f"block {rect} has no room for {ref}")
        fp.Move(pcbnew.VECTOR2I(MM(X0 + spot[0] - ox), MM(Y0 + spot[1] - oy)))
        obstacles.append(spot)


def add_text(b, text, x, y, size=0.8, layer=pcbnew.F_SilkS, angle=0, bold=False):
    t = pcbnew.PCB_TEXT(b)
    t.SetText(text); t.SetPosition(P(x, y)); t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size))); t.SetTextThickness(MM(max(0.16, size * (0.2 if bold else 0.15))))
    t.SetTextAngleDegrees(angle)
    b.Add(t)


def add_edge_keepout(b, w=0.6):
    """Rule area along the board edge: no tracks or vias (Freerouting honours it)."""
    for x1, y1, x2, y2 in [(0, 0, W, w), (0, H - w, W, H), (0, 0, w, H), (W - w, 0, W, H)]:
        z = pcbnew.ZONE(b)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False); z.SetDoNotAllowZoneFills(False)
        ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.B_Cu)
        z.SetLayerSet(ls)
        o = z.Outline(); o.NewOutline()
        for x, y in [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]:
            o.Append(MM(X0 + x), MM(Y0 + y))
        b.Add(z)


def add_zone(b, net, layer):
    z = pcbnew.ZONE(b)
    z.SetLayer(layer); z.SetNet(net)
    o = z.Outline(); o.NewOutline()
    for x, y in [(0, 0), (W, 0), (W, H), (0, H)]:
        o.Append(MM(X0 + x), MM(Y0 + y))
    z.SetLocalClearance(MM(0.25)); z.SetMinThickness(MM(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)
    z.SetThermalReliefGap(MM(0.3)); z.SetThermalReliefSpokeWidth(MM(0.5))
    b.Add(z)


def build(route=True):
    comps, nets = netlist()
    b = pcbnew.BOARD()
    ds = b.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    ds.m_TrackMinWidth = MM(0.15)
    ds.m_ViasMinSize = MM(0.5)
    ds.m_MinThroughDrill = MM(0.3)
    ds.m_MinClearance = MM(0.15)
    ds.m_CopperEdgeClearance = MM(0.3)
    ns = ds.m_NetSettings
    dflt = ns.GetDefaultNetclass()
    dflt.SetTrackWidth(MM(0.3)); dflt.SetClearance(MM(0.2)); dflt.SetViaDiameter(MM(0.6)); dflt.SetViaDrill(MM(0.3))
    add_outline(b)
    fps = {}
    for ref, c in sorted(comps.items()):
        fp = load_fp(c["fp"])
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        for k in ("LCSC",):
            v = c["fields"].get(k) or c["props"].get(k)
            if v:
                fp.SetField(k, v)
                fld = fp.GetField(k)
                fld.SetVisible(False); fld.SetLayer(pcbnew.F_Fab)
        if c["props"].get("dnp") is not None:
            fp.SetDNP(True)
            fp.SetExcludedFromBOM(True); fp.SetExcludedFromPosFiles(True)
        if ref.startswith("TP"):
            fp.SetExcludedFromBOM(True); fp.SetExcludedFromPosFiles(True)
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.6), MM(0.6)))
        fp.Reference().SetTextThickness(MM(0.1))
        fp.Reference().SetVisible(False)  # too dense for silkscreen; see the assembly drawing (F.Fab)
        b.Add(fp)
        fps[ref] = fp
    for ref, (x, y, rot) in FIXED.items():
        fps[ref].SetPosition(P(x, y))
        fps[ref].SetOrientationDegrees(rot)
    obstacles = [rel_box(fps[r]) for r in FIXED]
    for i, (x, y) in enumerate(PEGS):
        h = fps[f"H{i + 1}"]
        h.SetPosition(P(x, y))
        h.SetExcludedFromBOM(True); h.SetExcludedFromPosFiles(True)
        obstacles.append((x - 3.0, y - 3.0, x + 3.0, y + 3.0))  # room for the kuip corner plate and peg
    obstacles.append((28.6, 16.4, 39.6, 23.8))  # silkscreen title
    placed = set(FIXED) | {f"H{i + 1}" for i in range(len(PEGS))}
    for rect, refs in BLOCKS:
        place_block(fps, rect, refs, obstacles)
        placed.update(refs)
    missing = set(fps) - placed
    if missing:
        raise SystemExit(f"unplaced: {sorted(missing)}")
    # nets
    netobj = {}
    for name, nodes in sorted(nets.items()):
        if len(nodes) < 1:
            continue
        ni = pcbnew.NETINFO_ITEM(b, name)
        b.Add(ni)
        netobj[name] = ni
        for ref, pin in nodes:
            for pad in fps[ref].Pads():
                if pad.GetNumber() == pin:
                    pad.SetNet(ni)
    # silkscreen
    add_text(b, "P1-BASE", 34.0, 17.6, 1.0, bold=True)
    add_text(b, "v3.0", 34.0, 19.4, 1.0, bold=True)
    add_text(b, "energiegedrag.nl", 33.6, 21.6, 0.8)
    add_text(b, "CERN-OHL-P v2", 33.6, 23.1, 0.8)
    add_text(b, "METER", 4.6, 9.6, 0.8, bold=True)
    add_text(b, "P1 READER", 4.8, 46.8, 0.8, bold=True)
    add_text(b, "NeedForHeat P1-BASE v3.0", 20.0, 53.8, 1.0, layer=pcbnew.B_SilkS, bold=True)
    add_text(b, "energiegedrag.nl - CERN-OHL-P v2", 20.0, 51.8, 0.8, layer=pcbnew.B_SilkS)
    for t in b.GetDrawings():
        if isinstance(t, pcbnew.PCB_TEXT) and t.GetLayer() == pcbnew.B_SilkS:
            t.SetMirrored(True)
    out = os.path.join(PCBDIR, NAME + ".kicad_pcb")
    # features the enclosure needs (CoreInk-relative mm)
    import json
    feats = {"leds": {}, "jacks": {}}
    for ref in ("LED1", "LED2", "LED3"):
        pos = fps[ref].GetPosition()
        feats["leds"][ref] = [round(pcbnew.ToMM(pos.x) - X0, 2), round(pcbnew.ToMM(pos.y) - Y0, 2)]
    for ref in ("J2", "J3"):
        x1, y1, x2, y2 = rel_box(fps[ref])
        feats["jacks"][ref] = [round((x1 + x2) / 2, 2), round(x2 - x1, 2)]
    with open(os.path.join(ROOT, "enclosure", "pcb_features.json"), "w", encoding="utf8", newline=chr(10)) as f:
        json.dump(feats, f, indent=1)
    add_zone(b, netobj["/GND"], pcbnew.F_Cu)
    add_zone(b, netobj["/GND"], pcbnew.B_Cu)
    add_edge_keepout(b)
    b.BuildConnectivity()
    pcbnew.SaveBoard(out, b)
    print("placed board saved:", out)
    if route:
        autoroute(out)


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5


def stitch(b, pitch=1.5, via_d=0.6, drill=0.3, clr=0.25):
    """Add GND vias on a grid wherever they clear all other copper, tying the two GND pours together."""
    gnd = b.FindNet("/GND")
    obst = []  # (kind, geometry, half-width) in mm
    for t in b.GetTracks():
        if t.GetNetCode() == gnd.GetNetCode():
            continue
        if isinstance(t, pcbnew.PCB_VIA):
            p = t.GetPosition()
            obst.append(("c", (pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)), pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2))
        else:
            a, e = t.GetStart(), t.GetEnd()
            obst.append(("s", (pcbnew.ToMM(a.x), pcbnew.ToMM(a.y), pcbnew.ToMM(e.x), pcbnew.ToMM(e.y)),
                         pcbnew.ToMM(t.GetWidth()) / 2))
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            if pad.GetNetCode() == gnd.GetNetCode() and pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                continue
            r = max(pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())) / 2
            c = pad.GetPosition()
            obst.append(("c", (pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)), r + (0.2 if pad.GetNetCode() == gnd.GetNetCode() else 0)))
        if fp.GetReference().startswith("J"):
            bb = fp.GetBoundingBox(False)
            cx, cy = pcbnew.ToMM(bb.GetCenter().x), pcbnew.ToMM(bb.GetCenter().y)
            # connectors: keep vias out of their whole footprint
            obst.append(("r", (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
                               pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())), 0.0))
    for (x, y) in PEGS:
        obst.append(("c", (X0 + x, Y0 + y), 3.2))  # keep the kuip corner posts' area free
    n = 0
    y = 1.5
    while y <= H - 1.5:
        x = 1.5
        while x <= W - 1.5:
            px, py = X0 + x, Y0 + y
            ok = True
            for kind, g, hw in obst:
                if kind == "r":
                    if g[0] - 0.5 <= px <= g[2] + 0.5 and g[1] - 0.5 <= py <= g[3] + 0.5:
                        ok = False
                        break
                    continue
                d = ((px - g[0]) ** 2 + (py - g[1]) ** 2) ** 0.5 if kind == "c" else _seg_dist(px, py, *g)
                if d < hw + via_d / 2 + clr:
                    ok = False
                    break
            if ok:
                v = pcbnew.PCB_VIA(b)
                v.SetPosition(pcbnew.VECTOR2I(MM(px), MM(py)))
                v.SetWidth(MM(via_d)); v.SetDrill(MM(drill)); v.SetNet(gnd)
                b.Add(v)
                obst.append(("c", (px, py), via_d / 2))
                n += 1
            x += pitch
        y += pitch
    return n


def autoroute(path):
    b = pcbnew.LoadBoard(path)
    dsn = path[:-10] + ".dsn"
    ses = path[:-10] + ".ses"
    if not pcbnew.ExportSpecctraDSN(b, dsn):
        raise SystemExit("DSN export failed")
    cmd = [JAVA, "-jar", FREEROUTING, "-de", dsn, "-do", ses, "-mp", "30", "-mt", "0", "--gui.enabled=false"]
    print(" ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    print(r.stdout[-3000:], r.stderr[-3000:])
    if not os.path.exists(ses):
        raise SystemExit("Freerouting produced no SES file")
    if not pcbnew.ImportSpecctraSES(b, ses):
        raise SystemExit("SES import failed")

    filler = pcbnew.ZONE_FILLER(b)
    filler.Fill(b.Zones())
    n = stitch(b)
    filler.Fill(b.Zones())
    print("stitching vias:", n)
    pcbnew.SaveBoard(path, b)
    fix_islands(path)
    for f in (dsn, ses):
        os.remove(f)
    print("routed board saved:", path)


def fix_islands(path, step=0.25):
    """Give every GND pour fragment that has no via or through-hole pad at least one via."""
    b = pcbnew.LoadBoard(path)
    gnd = b.FindNet("/GND")
    filler = pcbnew.ZONE_FILLER(b)
    filler.Fill(b.Zones())
    anchors = [t.GetPosition() for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA) and t.GetNetCode() == gnd.GetNetCode()]
    anchors += [p.GetPosition() for f in b.GetFootprints() for p in f.Pads()
                if p.GetNetCode() == gnd.GetNetCode() and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
    added = 0
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetCode() != gnd.GetNetCode():
            continue
        polys = z.GetFilledPolysList(z.GetLayer())
        for i in range(polys.OutlineCount()):
            if any(polys.Contains(a, i) for a in anchors):
                continue
            bb = polys.Outline(i).BBox()
            done = False
            y = bb.GetTop()
            while y <= bb.GetBottom() and not done:
                x = bb.GetLeft()
                while x <= bb.GetRight():
                    pt = pcbnew.VECTOR2I(x, y)
                    # inside the fragment with 0.35 mm margin on all sides
                    ring = [(int(MM(0.4) * math.cos(k * math.pi / 8)), int(MM(0.4) * math.sin(k * math.pi / 8))) for k in range(16)]
                    if polys.Contains(pt, i) and all(polys.Contains(pcbnew.VECTOR2I(x + dx, y + dy), i) for dx, dy in ring):
                        v = pcbnew.PCB_VIA(b)
                        v.SetPosition(pt); v.SetWidth(MM(0.6)); v.SetDrill(MM(0.3)); v.SetNet(gnd)
                        b.Add(v)
                        anchors.append(pt)
                        added += 1
                        done = True
                        break
                    x += MM(step)
                y += MM(step)
            if not done:
                print("no room for a via in a GND fragment on", z.GetLayerName(),
                      [round(pcbnew.ToMM(v), 2) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom())])
    filler.Fill(b.Zones())
    pcbnew.SaveBoard(path, b)
    print("island vias added:", added)


def restitch(path):
    """Remove the stitching vias (GND vias without tracks) and stitch again."""
    b = pcbnew.LoadBoard(path)
    gnd = b.FindNet("/GND").GetNetCode()
    ends = set()
    for t in b.GetTracks():
        if not isinstance(t, pcbnew.PCB_VIA):
            ends.add((t.GetStart().x, t.GetStart().y)); ends.add((t.GetEnd().x, t.GetEnd().y))
    for t in list(b.GetTracks()):
        if isinstance(t, pcbnew.PCB_VIA) and t.GetNetCode() == gnd and (t.GetPosition().x, t.GetPosition().y) not in ends:
            b.Remove(t)
    filler = pcbnew.ZONE_FILLER(b)
    filler.Fill(b.Zones())
    print("stitching vias:", stitch(b))
    filler.Fill(b.Zones())
    pcbnew.SaveBoard(path, b)


if __name__ == "__main__":
    if "--islands" in sys.argv:
        fix_islands(os.path.join(PCBDIR, NAME + ".kicad_pcb"))
    elif "--stitch" in sys.argv:
        restitch(os.path.join(PCBDIR, NAME + ".kicad_pcb"))
    else:
        build(route="--no-route" not in sys.argv)
