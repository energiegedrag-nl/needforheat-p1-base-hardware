"""Tie GND pour islands that are connected to some GND pads/vias but not to the rest of GND (KiCad Python).

fix_islands() in gen_pcb.py only makes sure every pour fragment has a via; a fragment boxed in by signal tracks on
both layers can still form a GND group of its own (a pad, its fanout via and a bit of pour on each layer). This script
finds such groups and adds one via where a fragment of the group overlaps the main GND pour of the other layer, using
the real clearances (track/pad/via 0.2 mm, hole-to-hole 0.5 mm) instead of "inside the fill".

Run on a board with filled zones, i.e. after
  kicad-cli pcb drc --refill-zones --save-board ...
and run that DRC again afterwards (this script adds vias but does not refill):
  python tools/pcb_bridge_gnd.py
"""
import math
import os

import pcbnew

PCB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pcb", "needforheat-p1-base-hardware.kicad_pcb")
MM, T = pcbnew.FromMM, pcbnew.ToMM
VIA_D, DRILL, CLR, H2H, STEP = 0.56, 0.3, 0.22, 0.5, 0.05


def segd(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def main():
    b = pcbnew.LoadBoard(PCB)
    gnd = b.FindNet("GND")
    g = gnd.GetNetCode()
    layers = (pcbnew.F_Cu, pcbnew.B_Cu)
    frags = []  # (key, layer, polys, index)
    for z in b.Zones():
        if z.GetNetCode() != g or z.GetIsRuleArea():
            continue
        for L in layers:
            if z.IsOnLayer(L):
                ps = z.GetFilledPolysList(L)
                frags += [(("z", L, i), L, ps, i) for i in range(ps.OutlineCount())]

    par = {}

    def find(x):
        while par.setdefault(x, x) != x:
            x = par[x]
        return x

    def union(a, c):
        par[find(a)] = find(c)

    def hit(pt, L):
        return [k for k, LL, ps, i in frags if LL == L and ps.Contains(pt, i)]

    for k, *_ in frags:
        find(k)
    vias = [t for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA) and t.GetNetCode() == g]
    for v in vias:
        k = ("v", v.GetPosition().x, v.GetPosition().y)
        for L in layers:
            for h in hit(v.GetPosition(), L):
                union(k, h)
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode() != g:
                continue
            k = ("p", fp.GetReference(), p.GetNumber())
            for L in layers:
                if p.IsOnLayer(L):
                    for h in hit(p.GetPosition(), L):
                        union(k, h)
    for t in b.GetTracks():
        if t.GetNetCode() != g or isinstance(t, pcbnew.PCB_VIA):
            continue
        k = ("t", t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y)
        for q in (t.GetStart(), t.GetEnd()):
            for h in hit(q, t.GetLayer()):
                union(k, h)
            for v in vias:
                if v.GetPosition() == q:
                    union(k, ("v", q.x, q.y))
            for fp in b.GetFootprints():
                for p in fp.Pads():
                    if p.GetNetCode() == g and p.HitTest(q):
                        union(k, ("p", fp.GetReference(), p.GetNumber()))

    # the main group: the one with the largest pour area
    area = {}
    for k, L, ps, i in frags:
        area[find(k)] = area.get(find(k), 0) + ps.Outline(i).Area()
    main_root = max(area, key=area.get)
    main_frags = {L: [(ps, i) for k, LL, ps, i in frags if LL == L and find(k) == main_root] for L in layers}

    # obstacles: all non-GND copper
    obs, pads = [], []
    for t in b.GetTracks():
        if t.GetNetCode() == g:
            continue
        if isinstance(t, pcbnew.PCB_VIA):
            p = t.GetPosition()
            obs.append(({0, 1}, (T(p.x), T(p.y), T(p.x), T(p.y)), T(t.GetWidth(pcbnew.F_Cu)) / 2))
        else:
            obs.append(({0} if t.GetLayer() == pcbnew.F_Cu else {1},
                        (T(t.GetStart().x), T(t.GetStart().y), T(t.GetEnd().x), T(t.GetEnd().y)), T(t.GetWidth()) / 2))
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode() != g:
                bb = p.GetBoundingBox()
                pads.append((T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom())))
    holes = [(T(v.GetPosition().x), T(v.GetPosition().y), T(v.GetDrillValue()) / 2) for v in b.GetTracks()
             if isinstance(v, pcbnew.PCB_VIA)]
    holes += [(T(p.GetPosition().x), T(p.GetPosition().y), T(max(p.GetDrillSize().x, p.GetDrillSize().y)) / 2)
              for f in b.GetFootprints() for p in f.Pads() if p.GetDrillSize().x > 0]
    r = VIA_D / 2

    def clear(x, y):
        return (all(segd(x, y, *gm) >= hw + r + CLR for _, gm, hw in obs)
                and all((max(bb[0] - x, 0, x - bb[2]) ** 2 + max(bb[1] - y, 0, y - bb[3]) ** 2) ** 0.5 >= r + CLR for bb in pads)
                and all(math.hypot(x - hx, y - hy) >= hr + DRILL / 2 + H2H for hx, hy, hr in holes))

    added = 0
    for root in {find(k) for k, *_ in frags} - {main_root}:
        group = [(k, L, ps, i) for k, L, ps, i in frags if find(k) == root]
        members = [k for k in par if find(k) == root and k[0] == "p"]
        if not members:
            continue  # a dead island without pads: the pour removes it
        done = False
        for k, L, ps, i in group:
            other = pcbnew.B_Cu if L == pcbnew.F_Cu else pcbnew.F_Cu
            bb = ps.Outline(i).BBox()
            y = T(bb.GetTop())
            while y <= T(bb.GetBottom()) and not done:
                x = T(bb.GetLeft())
                while x <= T(bb.GetRight()):
                    pt = pcbnew.VECTOR2I(MM(x), MM(y))
                    if ps.Contains(pt, i) and any(mp.Contains(pt, mi) for mp, mi in main_frags[other]) and clear(x, y):
                        v = pcbnew.PCB_VIA(b)
                        v.SetPosition(pt)
                        v.SetWidth(MM(VIA_D)); v.SetDrill(MM(DRILL)); v.SetNet(gnd)
                        b.Add(v)
                        holes.append((x, y, DRILL / 2))
                        print("bridged GND group %s with a via at (%.2f, %.2f)" % (sorted(members), x, y))
                        added += 1
                        done = True
                        break
                    x += STEP
                y += STEP
            if done:
                break
        if not done:
            print("NO ROOM to bridge GND group", sorted(members), "- move a track or re-route")
    pcbnew.SaveBoard(PCB, b)
    print("bridge vias added:", added)


if __name__ == "__main__":
    main()
