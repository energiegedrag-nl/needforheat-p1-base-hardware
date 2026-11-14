"""Parametric enclosure ("kuip") for the NeedForHeat P1-BASE v3 on an M5Stack CoreInk.

Build with CadQuery 2.x:  python enclosure/kuip.py
Writes enclosure/fabrication/p1-base-kuip.{step,stl} and p1-base-lid.{step,stl}.

Frame: x to the right, y down from the top left corner of the CoreInk's back
(HAT edge up, as seen from behind), z up from the CoreInk's back surface.
All dimensions in mm. Values marked VERIFY come from drawings, not from a
measured part.
"""
import os

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fabrication")

# --- CoreInk (official M5Stack model + photo) ---------------------------
CI_W, CI_H, CI_R = 40.0, 56.0, 3.0
LEGO_HOLES = [(4, 4), (36, 4), (4, 52), (36, 52)]  # Ø4.85
MAGNETS = [(12.0, 11.0), (28.0, 17.0)]  # inside the CoreInk, VERIFY ± 2 mm

# --- P1-BASE board -------------------------------------------------------
GAP = 3.5  # CoreInk back -> PCB bottom (room for THT leads)
PCB_T = 1.6
PEGS = [(4, 4), (36, 4), (4, 52)]  # Ø2.2 NPTH in the PCB; the 4th corner has no peg (keys the PCB)
JACKS = [(15.5, "top"), (15.5, "bottom")]  # centre x of the RJ12 openings
JACK_W, JACK_H = 13.0, 11.6  # opening width; jack height above the PCB, VERIFY (C77859)
LEDS = []  # light holes in the lid, read from pcb_features.json (written by tools/gen_pcb.py)
_feat = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pcb_features.json")
if os.path.exists(_feat):
    import json
    with open(_feat, encoding="utf8") as _f:
        _d = json.load(_f)
    LEDS = [tuple(v) for v in _d["leds"].values()]
    JACKS = [(_d["jacks"]["J2"][0], "top"), (_d["jacks"]["J3"][0], "bottom")]

# --- enclosure ------------------------------------------------------------
CLR = 0.25  # clearance around CoreInk and PCB
WALL = 1.6
SKIRT = 3.0  # how far the wall continues down over the CoreInk's sides
POST = 6.0  # corner posts under the PCB, square
NOCK_D, NOCK_L = 4.6, 3.0  # tapered nocks into the LEGO holes
PEG_D = 2.0
DISC_D, DISC_T = 8.2, 1.1  # optional steel disc 8 x 1 mm
LID_T = 1.4
TOP_CLR = 0.6
Z_TOP = GAP + PCB_T + JACK_H + TOP_CLR


def slab(w, h, r, z0, z1, off=0.0):
    """Rounded rectangle around the CoreInk outline grown by `off`, from z0 to z1."""
    return (cq.Workplane("XY").workplane(offset=z0)
            .center(CI_W / 2, -CI_H / 2).rect(w + 2 * off, h + 2 * off)
            .extrude(z1 - z0).edges("|Z").fillet(r + off if r + off > 0.2 else 0.2))


def P(x, y):
    """Board coordinates to CadQuery XY (y up)."""
    return (x, -y)


def kuip():
    outer = slab(CI_W, CI_H, CI_R, -SKIRT, Z_TOP, CLR + WALL)
    inner = slab(CI_W, CI_H, CI_R, -SKIRT - 1, Z_TOP + 1, CLR)
    body = outer.cut(inner)
    # corner posts between CoreInk and PCB, joined to the wall
    for (x, y) in LEGO_HOLES:
        cx = min(max(x, POST / 2 - CLR), CI_W - POST / 2 + CLR)
        cy = min(max(y, POST / 2 - CLR), CI_H - POST / 2 + CLR)
        post = (cq.Workplane("XY").center(*P(cx, cy)).rect(POST + 2 * CLR, POST + 2 * CLR).extrude(GAP))
        body = body.union(post)
        nock = (cq.Workplane("XY").workplane(offset=-NOCK_L).center(*P(x, y)).circle(NOCK_D / 2 - 0.4)
                .workplane(offset=NOCK_L).circle(NOCK_D / 2).loft())
        body = body.union(nock)
        if (x, y) in PEGS:
            peg = cq.Workplane("XY").workplane(offset=GAP).center(*P(x, y)).circle(PEG_D / 2).extrude(PCB_T - 0.2)
            body = body.union(peg)
    # pads with pockets for optional steel discs, opposite the CoreInk magnets, tied to the wall by a rib
    for (x, y) in MAGNETS:
        pad = cq.Workplane("XY").center(*P(x, y)).circle(DISC_D / 2 + 1.0).extrude(1.6)
        rib = cq.Workplane("XY").center(*P(x / 2 if x < CI_W / 2 else (x + CI_W) / 2, y)).rect(
            x if x < CI_W / 2 else CI_W - x, 2.0).extrude(1.6)
        body = body.union(pad).union(rib)
        pocket = cq.Workplane("XY").workplane(offset=1.6 - DISC_T).center(*P(x, y)).circle(DISC_D / 2).extrude(DISC_T + 0.1)
        body = body.cut(pocket)
    # RJ12 openings, from the PCB top surface up to the top (the lid closes them)
    for (x, side) in JACKS:
        y = -WALL - CLR - 1 if side == "top" else CI_H + CLR - 1
        cut = (cq.Workplane("XY").workplane(offset=GAP + PCB_T)
               .center(*P(x, y + (WALL + 2) / 2)).rect(JACK_W, WALL + 2).extrude(Z_TOP))
        body = body.cut(cut)
    # cut-outs in the skirt: HAT edge (top), USB-C + Grove (bottom), dial and power switch (left in this view)
    for (x0, y0, w, h) in [(8, -5, 24, 6), (5, CI_H - 1, 26, 6), (-5, 12, 6, 15), (-5, 38, 6, 9)]:
        cut = cq.Workplane("XY").workplane(offset=-SKIRT - 1).center(*P(x0 + w / 2, y0 + h / 2)).rect(w, h).extrude(SKIRT + 1)
        body = body.cut(cut)
    # orientation mark on the outside: arrow pointing to the meter (HAT edge)
    mark = (cq.Workplane("XY").workplane(offset=Z_TOP).center(*P(CI_W / 2, -CLR - WALL / 2))
            .polygon(3, 2.4).extrude(-0.4))
    body = body.cut(mark)
    return body


def lid():
    plate = slab(CI_W, CI_H, CI_R, Z_TOP, Z_TOP + LID_T, CLR + WALL)
    lip = slab(CI_W, CI_H, CI_R, Z_TOP - 1.5, Z_TOP, CLR - 0.15).cut(
        slab(CI_W, CI_H, CI_R, Z_TOP - 2, Z_TOP + 1, CLR - 1.35))
    body = plate.union(lip)
    # tongues closing the RJ12 openings above the jacks
    for (x, side) in JACKS:
        y = -CLR - WALL / 2 if side == "top" else CI_H + CLR + WALL / 2
        t = cq.Workplane("XY").workplane(offset=Z_TOP).center(*P(x, y)).rect(JACK_W - 0.4, WALL).extrude(-(TOP_CLR + 0.3))
        body = body.union(t)
    for (x, y) in LEDS:
        body = body.cut(cq.Workplane("XY").workplane(offset=Z_TOP - 2).center(*P(x, y)).circle(1.0).extrude(LID_T + 3))
    return body


def main():
    os.makedirs(OUT, exist_ok=True)
    k, l = kuip(), lid()
    for name, part in (("p1-base-kuip", k), ("p1-base-lid", l)):
        cq.exporters.export(part, os.path.join(OUT, name + ".step"))
        cq.exporters.export(part, os.path.join(OUT, name + ".stl"), tolerance=0.02, angularTolerance=0.1)
        print("wrote", name)


if __name__ == "__main__":
    main()
