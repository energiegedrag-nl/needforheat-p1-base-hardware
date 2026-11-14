"""Parametric enclosure ("kuip") for the NeedForHeat P1-BASE v3 on an M5Stack CoreInk.

Build with CadQuery 2.x:  python enclosure/kuip.py
Writes enclosure/fabrication/p1-base-kuip.{step,stl} and p1-base-lid.{step,stl}.

Frame: x to the right, y down from the top left corner of the CoreInk's back
(HAT edge up, as seen from behind), z up from the CoreInk's back surface.
All dimensions in mm. Values marked VERIFY come from drawings, not from a
measured part.

Stacking: every enclosure in a NeedForHeat CoreInk stack has four LEGO-compatible posts underneath, at the
positions of the CoreInk's four LEGO holes. They are longer than the pins of the 2x8 bus header, so the posts
engage (and guide) before the pins do, and a loose module rests on its posts instead of its pins during shipping.
The lid of the P1-BASE repeats the CoreInk's back: four LEGO-compatible holes at the same positions and the bus
socket flush with the surface (a raised socket on the PCB), so a BatteryBASE fits behind it unchanged.
"""
import os

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fabrication")

# --- CoreInk (official M5Stack model + photo) ---------------------------
CI_W, CI_H, CI_R = 40.0, 56.0, 3.0
LEGO_HOLES = [(4, 4), (36, 4), (4, 52), (36, 52)]  # through holes; a LEGO Technic pin fits (measured)
LEGO_D = 4.85  # hole diameter
BUS = (33.97, 36.87)  # centre of the 2x8 bus (MI-BUS), from the official model and a photo
BUS_W, BUS_H = 5.08, 20.32  # 2 x 8 at 2.54 mm

# --- P1-BASE board -------------------------------------------------------
GAP = 2.5  # CoreInk back -> PCB bottom (RJ12 leads are 3.2 ± 0.3 mm below the seating plane: ≤ 1.9 mm below the PCB)
PCB_T = 1.6
PEGS = [(4, 4), (36, 4), (4, 52)]  # Ø2.2 NPTH in the PCB; the 4th corner has no peg (keys the PCB)
JACKS = [(20.0, "top"), (20.0, "bottom")]  # centre x of the RJ12 openings (centred)
JACK_W, JACK_H = 13.8, 11.45  # opening width (body 13.3); jack height above the PCB (EVERCOM 5301, C3097716)
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
POST_D, POST_L = 4.6, 7.0  # LEGO posts: core diameter, length (pins of the bus header stick out 6 mm)
RIB_D, RIB_W = 4.95, 0.45  # three crush ribs: light friction in the 4.85 mm hole, independent of print accuracy
PEG_D = 2.0
TUBE_D = 7.6  # tubes under the lid that form its LEGO holes
LID_T = 1.4
SOCKET_H = 13.59  # J1 Samtec ESQ-108-24-G-D: socket top above the board ("C", Samtec table 1)
# the lid's outer face is flush with the top of the raised socket, like the CoreInk's back
Z_TOP = GAP + PCB_T + SOCKET_H - LID_T
TOP_CLR = Z_TOP - (GAP + PCB_T + JACK_H)  # 0.74 mm above the RJ12 jacks
assert TOP_CLR >= 0.5


def slab(w, h, r, z0, z1, off=0.0):
    """Rounded rectangle around the CoreInk outline grown by `off`, from z0 to z1."""
    return (cq.Workplane("XY").workplane(offset=z0)
            .center(CI_W / 2, -CI_H / 2).rect(w + 2 * off, h + 2 * off)
            .extrude(z1 - z0).edges("|Z").fillet(r + off if r + off > 0.2 else 0.2))


def P(x, y):
    """Board coordinates to CadQuery XY (y up)."""
    return (x, -y)


def lego_post(x, y, z0, length=POST_L):
    """A LEGO-compatible post pointing down from z0: core, three crush ribs, a lead-in at the tip and a
    flared root against breaking off at the layer lines."""
    c = P(x, y)
    # starts 0.5 mm inside the part it hangs from, so the two fuse into one solid
    core = cq.Workplane("XY").workplane(offset=z0 + 0.5).center(*c).circle(POST_D / 2).extrude(-(length - 0.8 + 0.5))
    tip = (cq.Workplane("XY").workplane(offset=z0 - (length - 0.8)).center(*c).circle(POST_D / 2)
           .workplane(offset=-0.8).circle(POST_D / 2 - 0.6).loft())
    root = (cq.Workplane("XY").workplane(offset=z0).center(*c).circle(POST_D / 2 + 0.8)
            .workplane(offset=-0.8).circle(POST_D / 2).loft())
    post = core.union(tip).union(root)
    for k in range(3):
        rib = (cq.Workplane("XY").workplane(offset=z0 - 0.8).center(*c)
               .center((POST_D + RIB_D) / 4, 0).rect((RIB_D - POST_D) / 2 + 0.2, RIB_W)
               .extrude(-(length - 2.4)).rotate((c[0], c[1], 0), (c[0], c[1], 1), 120 * k))
        post = post.union(rib)
    return post


def kuip():
    outer = slab(CI_W, CI_H, CI_R, -SKIRT, Z_TOP, CLR + WALL)
    inner = slab(CI_W, CI_H, CI_R, -SKIRT - 1, Z_TOP + 1, CLR)
    body = outer.cut(inner)
    # corner posts between CoreInk and PCB, joined to the wall
    for (x, y) in LEGO_HOLES:
        # block from the corner of the wall to just past the LEGO hole, so it is part of the tray
        x0, x1 = (-CLR - 0.3, x + POST / 2) if x < CI_W / 2 else (x - POST / 2, CI_W + CLR + 0.3)
        y0, y1 = (-CLR - 0.3, y + POST / 2) if y < CI_H / 2 else (y - POST / 2, CI_H + CLR + 0.3)
        post = (cq.Workplane("XY").center(*P((x0 + x1) / 2, (y0 + y1) / 2)).rect(x1 - x0, y1 - y0).extrude(GAP))
        body = body.union(post)
        body = body.union(lego_post(x, y, 0.0))
        if (x, y) in PEGS:
            peg = cq.Workplane("XY").workplane(offset=GAP).center(*P(x, y)).circle(PEG_D / 2).extrude(PCB_T - 0.2)
            body = body.union(peg)
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
    # notch the lip above the RJ12 jacks, which reach the board edge
    for (x, side) in JACKS:
        y = 0.0 if side == "top" else CI_H
        lip = lip.cut(cq.Workplane("XY").workplane(offset=Z_TOP - 2).center(*P(x, y)).rect(JACK_W + 0.4, 6).extrude(2))
    body = plate.union(lip)
    # tongues closing the RJ12 openings above the jacks
    for (x, side) in JACKS:
        y = -CLR - WALL / 2 if side == "top" else CI_H + CLR + WALL / 2
        t = cq.Workplane("XY").workplane(offset=Z_TOP).center(*P(x, y)).rect(JACK_W - 0.4, WALL).extrude(-(TOP_CLR - 0.2))  # stops 0.2 mm above the jack
        body = body.union(t)
    for (x, y) in LEDS:
        body = body.cut(cq.Workplane("XY").workplane(offset=Z_TOP - 2).center(*P(x, y)).circle(1.0).extrude(LID_T + 3))
    # LEGO holes like on the CoreInk's back: tubes under the lid, as deep as a post is long (+0.5)
    depth = POST_L + 0.5
    for (x, y) in LEGO_HOLES:
        tube = cq.Workplane("XY").workplane(offset=Z_TOP + LID_T - depth).center(*P(x, y)).circle(TUBE_D / 2).extrude(depth - LID_T)
        body = body.union(tube)
        body = body.cut(cq.Workplane("XY").workplane(offset=Z_TOP + LID_T - depth - 0.1).center(*P(x, y))
                        .circle(LEGO_D / 2).extrude(depth + 0.2))
    # cut-out for the raised bus socket, whose top is flush with the lid (VERIFY against the chosen part)
    body = body.cut(cq.Workplane("XY").workplane(offset=Z_TOP - 2).center(*P(*BUS)).rect(BUS_W + 0.5, BUS_H + 0.5)
                    .extrude(LID_T + 3))
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
