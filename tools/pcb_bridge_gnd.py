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
import heapq
import math
import os

import numpy as np
import pcbnew

PCB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pcb", "needforheat-p1-base-hardware.kicad_pcb")
MM, T = pcbnew.FromMM, pcbnew.ToMM
VIA_D, DRILL, CLR, H2H, STEP = 0.56, 0.3, 0.22, 0.5, 0.05
# maze fallback: GND track width, netclass clearance, track-to-hole and copper-to-edge clearance, grid, search margin
TRK_W, NET_CLR, HOLE_CLR, EDGE_CLR, GRID, WIN = 0.25, 0.2, 0.25, 0.3, 0.05, 6.0


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


    # all copper as plain numbers: kind, net, layer indices, segment (a == b for vias), half width, pad box, object
    items = []
    for t in b.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            p = t.GetPosition()
            items.append(dict(kind="via", net=t.GetNetCode(), lay={0, 1}, seg=(T(p.x), T(p.y), T(p.x), T(p.y)),
                              hw=T(t.GetWidth(pcbnew.F_Cu)) / 2, drill=T(t.GetDrillValue()) / 2, obj=t))
        else:
            items.append(dict(kind="trk", net=t.GetNetCode(), lay={0} if t.GetLayer() == pcbnew.F_Cu else {1},
                              seg=(T(t.GetStart().x), T(t.GetStart().y), T(t.GetEnd().x), T(t.GetEnd().y)),
                              hw=T(t.GetWidth()) / 2, width=t.GetWidth(), obj=t))
    for fp in b.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            items.append(dict(kind="pad", net=p.GetNetCode(), lay={i for i, L in enumerate(layers) if p.IsOnLayer(L)},
                              box=(T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom())),
                              drill=T(max(p.GetDrillSize().x, p.GetDrillSize().y)) / 2, obj=p,
                              pos=(T(p.GetPosition().x), T(p.GetPosition().y))))
    ctx = dict(b=b, gnd=gnd, items=items, removed=[])
    r = VIA_D / 2

    def clear(x, y):
        for it in items:
            if it["net"] == g or it.get("gone"):
                continue
            if it["kind"] == "pad":
                bb = it["box"]
                if (max(bb[0] - x, 0, x - bb[2]) ** 2 + max(bb[1] - y, 0, y - bb[3]) ** 2) ** 0.5 < r + CLR:
                    return False
            elif segd(x, y, *it["seg"]) < it["hw"] + r + CLR:
                return False
        return all(math.hypot(x - hx, y - hy) >= hr + DRILL / 2 + H2H for hx, hy, hr in holes(items))

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
                        add_via(ctx, x, y, g)
                        print("bridged GND group %s with a via at (%.2f, %.2f)" % (sorted(members), x, y))
                        added += 1
                        done = True
                        break
                    x += STEP
                y += STEP
            if done:
                break
        if not done:
            done = maze_bridge(ctx, group, main_frags, sorted(members))
        if not done:
            print("NO ROOM to bridge GND group", sorted(members), "- move a track or re-route")
    for it in ctx["removed"]:
        b.Remove(it["obj"])
    pcbnew.SaveBoard(PCB, b)
    print("bridge vias added:", added + sum(1 for it in items if it["kind"] == "via" and it.get("new")))


def holes(items, skip_net=None):
    return [(*it["seg"][:2], it["drill"]) if it["kind"] == "via" else (*it["pos"], it["drill"])
            for it in items if it.get("drill", 0) > 0 and not it.get("gone") and it["net"] != skip_net]


def add_via(ctx, x, y, net):
    v = pcbnew.PCB_VIA(ctx["b"])
    v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
    v.SetWidth(MM(VIA_D)); v.SetDrill(MM(DRILL)); v.SetNetCode(net)
    ctx["b"].Add(v)
    ctx["items"].append(dict(kind="via", net=net, lay={0, 1}, seg=(x, y, x, y), hw=VIA_D / 2, drill=DRILL / 2, obj=v,
                             new=True))


def add_track(ctx, a, c, li, net, w):
    t = pcbnew.PCB_TRACK(ctx["b"])
    t.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1]))); t.SetEnd(pcbnew.VECTOR2I(MM(c[0]), MM(c[1])))
    t.SetWidth(MM(w)); t.SetLayer((pcbnew.F_Cu, pcbnew.B_Cu)[li]); t.SetNetCode(net)
    ctx["b"].Add(t)
    ctx["items"].append(dict(kind="trk", net=net, lay={li}, seg=(*a, *c), hw=w / 2, width=MM(w), obj=t, new=True))


class Grid:
    """A GRID mm raster of a window, with per-layer distances to copper of other nets."""

    def __init__(self, ctx, x0, y0, x1, y1):
        eb = ctx["b"].GetBoardEdgesBoundingBox()
        m = EDGE_CLR + VIA_D / 2
        x0, y0 = max(x0, T(eb.GetLeft()) + m), max(y0, T(eb.GetTop()) + m)
        x1, y1 = min(x1, T(eb.GetRight()) - m), min(y1, T(eb.GetBottom()) - m)
        self.xs, self.ys = np.arange(x0, x1, GRID), np.arange(y0, y1, GRID)
        self.X, self.Y = np.meshgrid(self.xs, self.ys)

    def cover(self, it, grow=0.0):
        """Cells within `grow` of the item's copper."""
        X, Y = self.X, self.Y
        if it["kind"] == "pad":
            l, t, r, b = it["box"]
            d = np.hypot(np.maximum(np.maximum(l - X, 0), X - r), np.maximum(np.maximum(t - Y, 0), Y - b))
            if grow < 0:  # strictly inside, `-grow` from the edge
                return (X >= l - grow) & (X <= r + grow) & (Y >= t - grow) & (Y <= b + grow)
            return d <= grow
        ax, ay, bx, by = it["seg"]
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = np.zeros(X.shape) if L == 0 else np.clip(((X - ax) * dx + (Y - ay) * dy) / L, 0, 1)
        return np.hypot(X - ax - t * dx, Y - ay - t * dy) <= it["hw"] + grow

    def free(self, ctx, net, w, skip=()):
        """Track (width w) and via freedom for `net`, ignoring items in `skip` (rip-up candidates)."""
        X = self.X
        gap = [np.full(X.shape, 1e9), np.full(X.shape, 1e9)]
        for it in ctx["items"]:
            if it["net"] == net or it.get("gone") or id(it) in skip:
                continue
            if it["kind"] == "pad":
                l, t, r, b = it["box"]
                d = np.hypot(np.maximum(np.maximum(l - X, 0), X - r), np.maximum(np.maximum(t - self.Y, 0), self.Y - b))
            else:
                ax, ay, bx, by = it["seg"]
                dx, dy = bx - ax, by - ay
                L = dx * dx + dy * dy
                tt = np.zeros(X.shape) if L == 0 else np.clip(((X - ax) * dx + (self.Y - ay) * dy) / L, 0, 1)
                d = np.hypot(X - ax - tt * dx, self.Y - ay - tt * dy) - it["hw"]
            for li in it["lay"]:
                gap[li] = np.minimum(gap[li], d)
        hole_o, hole_a = np.full(X.shape, 1e9), np.full(X.shape, 1e9)
        for hx, hy, hr in holes(ctx["items"]):
            hole_a = np.minimum(hole_a, np.hypot(X - hx, self.Y - hy) - hr)
        for hx, hy, hr in holes(ctx["items"], skip_net=net):
            hole_o = np.minimum(hole_o, np.hypot(X - hx, self.Y - hy) - hr)
        free = [(gp >= NET_CLR + w / 2) & (hole_o >= HOLE_CLR + w / 2) for gp in gap]
        via_ok = (gap[0] >= NET_CLR + VIA_D / 2) & (gap[1] >= NET_CLR + VIA_D / 2) & (hole_a >= DRILL / 2 + H2H)
        return free, via_ok

    def search(self, free, via_ok, src, is_dst):
        """Dijkstra from the src cells (per-layer masks) to the first cell where is_dst(li, i, j); returns
        (cost, path of (layer, i, j)) or None."""
        ny, nx = self.X.shape
        cost, prev, pq = {}, {}, []
        for li in (0, 1):
            for i, j in zip(*np.nonzero(src[li] & free[li])):
                cost[(li, i, j)] = 0.0
                pq.append((0.0, li, i, j))
        heapq.heapify(pq)
        while pq:
            c, li, i, j = heapq.heappop(pq)
            if c > cost[(li, i, j)]:
                continue
            if c > 0 and is_dst(li, i, j):
                path = [(li, i, j)]
                while path[-1] in prev:
                    path.append(prev[path[-1]])
                return c, path[::-1]
            nb = [(li, i + di, j + dj, math.hypot(di, dj)) for di in (-1, 0, 1) for dj in (-1, 0, 1) if di or dj]
            if via_ok[i, j]:
                nb.append((1 - li, i, j, 30.0))
            for l2, i2, j2, w in nb:
                if 0 <= i2 < ny and 0 <= j2 < nx and free[l2][i2, j2] and c + w < cost.get((l2, i2, j2), 1e18):
                    cost[(l2, i2, j2)] = c + w
                    prev[(l2, i2, j2)] = (li, i, j)
                    heapq.heappush(pq, (c + w, l2, i2, j2))
        return None

    def emit(self, ctx, path, net, w):
        """Straight runs become tracks, layer changes vias; returns (segments, vias) added."""
        def xy(p):
            return float(self.xs[p[2]]), float(self.ys[p[1]])
        runs, nvia = [[path[0]]], 0
        for p in path[1:]:
            rr = runs[-1]
            if p[0] != rr[-1][0]:
                add_via(ctx, *xy(p), net)
                nvia += 1
                runs.append([p])
            elif len(rr) >= 2 and (np.sign(rr[-1][1] - rr[-2][1]), np.sign(rr[-1][2] - rr[-2][2])) == (p[1] - rr[-1][1], p[2] - rr[-1][2]):
                rr[-1] = p
            else:
                rr.append(p)
        nseg = 0
        for rr in runs:
            for a, c in zip(rr, rr[1:]):
                add_track(ctx, xy(a), xy(c), a[0], net, w)
                nseg += 1
        return nseg, nvia


def maze_bridge(ctx, group, main_frags, members):
    """Fallback when no single via fits: a shortest GND track (TRK_W, vias allowed) from the group to the main pour.
    If even that is boxed in, rip up the tracks of one signal net in the window, lay the GND track and re-route that
    net around it (cheapest candidate first). Returns True on success."""
    layers = (pcbnew.F_Cu, pcbnew.B_Cu)
    g = ctx["gnd"].GetNetCode()
    bbs = [ps.Outline(i).BBox() for _, _, ps, i in group]
    gr = Grid(ctx, min(T(bb.GetLeft()) for bb in bbs) - WIN, min(T(bb.GetTop()) for bb in bbs) - WIN,
              max(T(bb.GetRight()) for bb in bbs) + WIN, max(T(bb.GetBottom()) for bb in bbs) + WIN)
    src = [np.zeros(gr.X.shape, bool), np.zeros(gr.X.shape, bool)]
    # cells inside the group's own pour (polygon test on a coarse pre-filter by bbox)
    for _, L, ps, k in group:
        li = layers.index(L)
        bb = ps.Outline(k).BBox()
        sel = ((gr.X >= T(bb.GetLeft())) & (gr.X <= T(bb.GetRight())) & (gr.Y >= T(bb.GetTop())) & (gr.Y <= T(bb.GetBottom())))
        for i, j in zip(*np.nonzero(sel)):
            if ps.Contains(pcbnew.VECTOR2I(MM(float(gr.xs[j])), MM(float(gr.ys[i]))), k):
                src[li][i, j] = True
    memo = {}

    def is_main(li, i, j):
        if (li, i, j) not in memo:
            pt = pcbnew.VECTOR2I(MM(float(gr.xs[j])), MM(float(gr.ys[i])))
            memo[(li, i, j)] = any(ps.Contains(pt, k) for ps, k in main_frags[layers[li]])
        return memo[(li, i, j)]

    free, via_ok = gr.free(ctx, g, TRK_W)
    hit = gr.search(free, via_ok, src, is_main)
    if hit:
        nseg, nvia = gr.emit(ctx, hit[1], g, TRK_W)
        print("bridged GND group %s with a %.2f mm track (%d segments, %d vias)" % (members, TRK_W, nseg, nvia))
        return True

    # rip-up: one signal net at a time, cheapest GND path first
    inwin = lambda it: gr.cover(it, 0.5).any()  # noqa: E731
    cands = {}
    for it in ctx["items"]:
        if it["kind"] == "trk" and it["net"] != g and not it.get("gone") and inwin(it):
            cands.setdefault(it["net"], []).append(it)
    tries = []
    for net, trks in cands.items():
        free, via_ok = gr.free(ctx, g, TRK_W, skip={id(t) for t in trks})
        hit = gr.search(free, via_ok, src, is_main)
        if hit:
            tries.append((hit[0], net, hit[1], trks))
    for cost, net, path, trks in sorted(tries, key=lambda t: t[0]):
        n_items = len(ctx["items"])
        nseg, nvia = gr.emit(ctx, path, g, TRK_W)
        new_gnd = ctx["items"][n_items:]
        # the tracks of `net` that now clash with the new GND copper
        clash = [t for t in trks if any(t["lay"] & n["lay"] and seg_gap(t["seg"], n["seg"]) < t["hw"] + n["hw"] + NET_CLR
                                        for n in new_gnd)]
        for t in clash:
            t["gone"] = True
        if reconnect(ctx, net, clash):
            name = trks[0]["obj"].GetNetname()
            print("bridged GND group %s with a %.2f mm track (%d segments, %d vias) after re-routing %d track(s) of %s"
                  % (members, TRK_W, nseg, nvia, len(clash), name))
            ctx["removed"] += clash
            return True
        # undo: drop what this attempt added, restore the ripped tracks
        for it in ctx["items"][n_items:]:
            ctx["b"].Remove(it["obj"])
        del ctx["items"][n_items:]
        for t in clash:
            t.pop("gone")
    return False


def seg_gap(s, u):
    """Smallest distance between two segments (centre lines)."""
    if segs_cross(s, u):
        return 0.0
    return min(segd(*s[:2], *u), segd(*s[2:], *u), segd(*u[:2], *s), segd(*u[2:], *s))


def segs_cross(s, u):
    def orient(ax, ay, bx, by, cx, cy):
        return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    d1, d2 = orient(*s, *u[:2]), orient(*s, *u[2:])
    d3, d4 = orient(*u, *s[:2]), orient(*u, *s[2:])
    return d1 * d2 < 0 and d3 * d4 < 0


def touches(a, c):
    """Copper of two items of one net connects (track ends inside the other item, shared layer)."""
    if not (a["lay"] & c["lay"]):
        return False
    if a["kind"] == "pad" and c["kind"] == "pad":
        return False
    if a["kind"] == "pad":
        a, c = c, a
    ends = [a["seg"][:2], a["seg"][2:]] if a["kind"] == "trk" else [a["seg"][:2]]
    if c["kind"] == "pad":
        return any(c["obj"].HitTest(pcbnew.VECTOR2I(MM(x), MM(y))) for x, y in ends)
    ends_c = [c["seg"][:2], c["seg"][2:]] if c["kind"] == "trk" else [c["seg"][:2]]
    # an end must lie clearly inside the other copper (an end on the edge is not a connection for KiCad)
    return (any(segd(x, y, *c["seg"]) <= c["hw"] - 0.03 for x, y in ends)
            or any(segd(x, y, *a["seg"]) <= a["hw"] - 0.03 for x, y in ends_c))


def drop_stubs(ctx, net, mine):
    """Mark tracks of `net` with an end that touches nothing else of the net as gone (repeat until none)."""
    while True:
        live = [it for it in mine if not it.get("gone")]
        stubs = []
        for t in live:
            if t["kind"] != "trk":
                continue
            for end in (t["seg"][:2], t["seg"][2:]):
                probe = dict(kind="trk", net=net, lay=t["lay"], seg=(*end, *end), hw=0)
                if not any(o is not t and touches(probe, o) for o in live):
                    stubs.append(t)
                    break
        if not stubs:
            return
        for t in stubs:
            t["gone"] = True
            if not t.get("new"):
                ctx["removed"].append(t)
            else:
                ctx["b"].Remove(t["obj"])


def reconnect(ctx, net, ripped):
    """Re-route `net` after its `ripped` tracks are gone: join its pieces again with GRID maze tracks."""
    w = max(min(it["hw"] * 2 for it in ripped), 0.2) if ripped else TRK_W
    xs = [v for it in ripped for v in (it["seg"][0], it["seg"][2])]
    ys = [v for it in ripped for v in (it["seg"][1], it["seg"][3])]
    gr = Grid(ctx, min(xs) - WIN, min(ys) - WIN, max(xs) + WIN, max(ys) + WIN)
    for _ in range(len(ripped) + 2):
        mine = [it for it in ctx["items"] if it["net"] == net and not it.get("gone")]
        par = list(range(len(mine)))

        def find(x):
            while par[x] != x:
                par[x] = par[par[x]]
                x = par[x]
            return x
        for i in range(len(mine)):
            for j in range(i + 1, len(mine)):
                if touches(mine[i], mine[j]):
                    par[find(i)] = find(j)
        comps = {}
        for i, it in enumerate(mine):
            comps.setdefault(find(i), []).append(it)
        if len(comps) == 1:
            drop_stubs(ctx, net, mine)
            return True
        parts = sorted(comps.values(), key=len)
        free, via_ok = gr.free(ctx, net, w)

        def mask(its):
            m = [np.zeros(gr.X.shape, bool), np.zeros(gr.X.shape, bool)]
            for it in its:
                c = gr.cover(it, -0.06)
                for li in it["lay"]:
                    m[li] |= c
            return m
        src = mask(parts[0])
        dst = mask([it for p in parts[1:] for it in p])
        if not (src[0].any() or src[1].any()):
            return False
        hit = gr.search(free, via_ok, src, lambda li, i, j: dst[li][i, j])
        if not hit:
            return False
        gr.emit(ctx, hit[1], net, w)
    return False


if __name__ == "__main__":
    main()
