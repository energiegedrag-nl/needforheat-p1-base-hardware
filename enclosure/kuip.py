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
PEGS = [(36, 4), (4, 52), (36, 52)]  # Ø2.2 NPTH in the PCB; the top-left corner has no peg (keys the PCB; LEDs there)
JACKS = [(20.0, "top"), (20.0, "bottom")]  # centre x of the RJ12 openings (centred)
JACK_W, JACK_H = 13.8, 11.45  # opening width (body 13.3); jack height above the PCB (EVERCOM 5301, C3097716)
LEDS = []  # side-looking LEDs at the top board edge, read from pcb_features.json (written by tools/gen_pcb.py)
LED_LENS_Z = 0.5  # lens centre above the PCB (LTST-S220, VERIFY against the Lite-On drawing)
LED_HOLE_W, LED_HOLE_H = 2.0, 1.4  # light window in the top wall, generous for the unverified lens height
_feat = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pcb_features.json")
if os.path.exists(_feat):
    import json
    with open(_feat, encoding="utf8") as _f:
        _d = json.load(_f)
    LEDS = [tuple(v) for v in _d["leds"].values()]
    JACKS = [(_d["jacks"]["J2"][0], "top"), (_d["jacks"]["J3"][0], "bottom")]

# --- enclosure ------------------------------------------------------------
# The outside is exactly the CoreInk outline (40 x 56 mm, R3), so every module's back equals the CoreInk's back and any
# BASE that fits a bare CoreInk also fits behind this one. No skirt: the posts and the bus header hold the module.
CLR = 0.25  # clearance between the walls and the PCB (PCB = CoreInk outline minus WALL + CLR on every side)
WALL = 1.6
POST = 6.0  # corner posts under the PCB, square
POST_D, POST_L = 4.6, 7.0  # LEGO posts: core diameter, length (pins of the bus header stick out 6 mm)
RIB_D, RIB_W = 4.95, 0.45  # three crush ribs: light friction in the 4.85 mm hole, independent of print accuracy
PEG_D = 2.0
CORNER = 7.8  # corner pillars of the lid: square from the outline corner, around the LEGO hole (hole axis at 4, 4)
# LEGO Technic hole in the lid, so a real Technic pin clicks in like on the CoreInk (LEGO standard values, VERIFY on a
# test print): Ø4.8 bore (we keep the measured 4.85), Ø6.2 x 0.8 counterbore at the entry, and a Ø6.2 groove where
# the pin's slotted end snaps in, 7.8 mm (one Technic module) below the entry
TECH_CB_D, TECH_CB_T = 6.2, 0.8
TECH_L = 7.8
# snap fit: bumps on the lid's lip click into grooves in the long walls
LIP_H, LIP_T = 1.8, 1.0  # lip height below the lid, thickness (thin enough to flex)
SNAP_R, SNAP_P = 0.6, 0.35  # bump radius and how far it sticks out past the lip
SNAP_L = 7.0  # bump length
SNAP_Y = [14.0, 42.0]  # bump centres along the long walls
GROOVE_D = 0.55  # groove depth in the wall: the bump sits in it with 0.2 mm to spare
LID_T = 1.4
SOCKET_H = 13.59  # J1 Samtec ESQ-108-24-G-D: socket top above the board ("C", Samtec table 1)
# the lid's outer face is flush with the top of the raised socket, like the CoreInk's back
Z_TOP = GAP + PCB_T + SOCKET_H - LID_T
TOP_CLR = Z_TOP - (GAP + PCB_T + JACK_H)  # 0.74 mm above the RJ12 jacks
assert TOP_CLR >= 0.5
# shipping: each module goes loose (not stacked) in a letterbox parcel (PostNL brievenbuspakje, max. 32 mm thick);
# 27 mm leaves ≥ 5 mm for the box and padding. Thickness = lid top to the tips of the LEGO posts.
SHIP_MAX = 27.0
SHIP_T = Z_TOP + LID_T + POST_L
assert SHIP_T <= SHIP_MAX, f"P1-BASE is {SHIP_T:.1f} mm thick, more than {SHIP_MAX} mm for a letterbox parcel"


def slab(w, h, r, z0, z1, off=0.0):
    """Rounded rectangle around the CoreInk outline grown by `off`, from z0 to z1."""
    return (cq.Workplane("XY").workplane(offset=z0)
            .center(CI_W / 2, -CI_H / 2).rect(w + 2 * off, h + 2 * off)
            .extrude(z1 - z0).edges("|Z").fillet(r + off if r + off > 0.2 else 0.2))


def P(x, y):
    """Board coordinates to CadQuery XY (y up)."""
    return (x, -y)


def lego_post(x, y, z0, length=POST_L):
    """A LEGO-compatible post pointing down from z0: core, three crush ribs and a lead-in at the tip.
    No flared root: below z0 is the CoreInk's back, and the post grows out of the 6 x 6 mm corner block above it."""
    c = P(x, y)
    # starts 0.5 mm inside the part it hangs from, so the two fuse into one solid
    core = cq.Workplane("XY").workplane(offset=z0 + 0.5).center(*c).circle(POST_D / 2).extrude(-(length - 0.8 + 0.5))
    tip = (cq.Workplane("XY").workplane(offset=z0 - (length - 0.8)).center(*c).circle(POST_D / 2)
           .workplane(offset=-0.8).circle(POST_D / 2 - 0.6).loft())
    post = core.union(tip)
    for k in range(3):
        rib = (cq.Workplane("XY").workplane(offset=z0 - 0.8).center(*c)
               .center((POST_D / 2 - 0.1 + RIB_D / 2) / 2, 0).rect((RIB_D - POST_D) / 2 + 0.1, RIB_W)  # from inside the core to RIB_D / 2
               .extrude(-(length - 2.4)).rotate((c[0], c[1], 0), (c[0], c[1], 1), 120 * k))
        post = post.union(rib)
    return post


def corner_box(x, y, z0, z1):
    """Square region from the outline corner nearest to (x, y) to just past the LEGO hole, between z0 and z1."""
    x0, x1 = (0.0, CORNER) if x < CI_W / 2 else (CI_W - CORNER, CI_W)
    y0, y1 = (0.0, CORNER) if y < CI_H / 2 else (CI_H - CORNER, CI_H)
    return cq.Workplane("XY").workplane(offset=z0).center(*P((x0 + x1) / 2, (y0 + y1) / 2)).rect(x1 - x0, y1 - y0).extrude(z1 - z0)


Z_LID = Z_TOP + LID_T  # outer face of the lid
Z_CORNER = Z_LID - (TECH_L + 0.5)  # bottom of the lid's corner pillars


def kuip():
    body = slab(CI_W, CI_H, CI_R, 0.0, Z_TOP).cut(slab(CI_W, CI_H, CI_R, -1, Z_TOP + 1, -WALL))
    # corner blocks between CoreInk and PCB, joined to the walls; LEGO posts underneath; pegs that key the PCB
    for (x, y) in LEGO_HOLES:
        x0, x1 = (WALL - 0.3, x + POST / 2) if x < CI_W / 2 else (x - POST / 2, CI_W - WALL + 0.3)
        y0, y1 = (WALL - 0.3, y + POST / 2) if y < CI_H / 2 else (y - POST / 2, CI_H - WALL + 0.3)
        block = cq.Workplane("XY").center(*P((x0 + x1) / 2, (y0 + y1) / 2)).rect(x1 - x0, y1 - y0).extrude(GAP)
        body = body.union(block).union(lego_post(x, y, 0.0))
        if (x, y) in PEGS:
            body = body.union(cq.Workplane("XY").workplane(offset=GAP).center(*P(x, y)).circle(PEG_D / 2).extrude(PCB_T - 0.2))
        # the lid's corner pillar takes over the top of the corner
        body = body.cut(corner_box(x, y, Z_CORNER - 0.2, Z_TOP + 1))
    # RJ12 openings through the top and bottom walls, from 0.3 mm below the PCB top surface up (the lid closes them);
    # the jack front sticks out 0.5 mm past the board edge into the wall
    for (x, side) in JACKS:
        yc = WALL / 2 if side == "top" else CI_H - WALL / 2
        body = body.cut(cq.Workplane("XY").workplane(offset=GAP + PCB_T - 0.3).center(*P(x, yc))
                        .rect(JACK_W, WALL + 2).extrude(Z_TOP))
    # light windows for the side-looking LEDs in the top wall
    for (x, y) in LEDS:
        z = GAP + PCB_T + LED_LENS_Z
        body = body.cut(cq.Workplane("XY").workplane(offset=z - LED_HOLE_H / 2).center(*P(x, WALL / 2))
                        .rect(LED_HOLE_W, WALL + 1.0).extrude(LED_HOLE_H))
    # snap-fit grooves for the lid's bumps (inner face of the two long walls)
    zb = Z_TOP - LIP_H / 2
    for x in (WALL - GROOVE_D / 2, CI_W - WALL + GROOVE_D / 2):
        for y in SNAP_Y:
            body = body.cut(cq.Workplane("XY").workplane(offset=zb - SNAP_R - 0.15).center(*P(x, y))
                            .rect(GROOVE_D + 0.02, SNAP_L + 1.0).extrude(2 * SNAP_R + 0.3))
    # pry notch in the top of the bottom wall, to lift the lid off
    body = body.cut(cq.Workplane("XY").workplane(offset=Z_TOP - 0.8).center(*P(24.0, CI_H - WALL / 2))
                    .rect(6.0, WALL + 1.0).extrude(1.0))
    return body


def technic_hole(x, y):
    """LEGO Technic hole from the lid's outer face down: counterbore, bore, snap groove (see TECH_*)."""
    c = P(x, y)
    h = cq.Workplane("XY").workplane(offset=Z_CORNER - 0.1).center(*c).circle(LEGO_D / 2).extrude(Z_LID - Z_CORNER + 0.2)
    h = h.union(cq.Workplane("XY").workplane(offset=Z_LID - TECH_CB_T).center(*c).circle(TECH_CB_D / 2).extrude(1))
    return h.union(cq.Workplane("XY").workplane(offset=Z_LID - TECH_L).center(*c).circle(TECH_CB_D / 2).extrude(TECH_CB_T))


def lid():
    body = slab(CI_W, CI_H, CI_R, Z_TOP, Z_LID)
    # lip inside the tray walls, with snap bumps on its outside along the long sides
    off = -(WALL + 0.15)
    lip = slab(CI_W, CI_H, CI_R, Z_TOP - LIP_H, Z_TOP, off).cut(slab(CI_W, CI_H, CI_R, Z_TOP - LIP_H - 0.5, Z_TOP + 1, off - LIP_T))
    zb = Z_TOP - LIP_H / 2
    for x, sgn in ((WALL + 0.15, -1), (CI_W - WALL - 0.15, 1)):
        for y in SNAP_Y:
            cx = x + sgn * (SNAP_P - SNAP_R)
            lip = lip.union(cq.Workplane("XY").add(cq.Solid.makeCylinder(
                SNAP_R, SNAP_L, cq.Vector(cx, -y - SNAP_L / 2, zb), cq.Vector(0, 1, 0))))
    # notch the lip above the RJ12 jacks, which reach the board edge
    for (x, side) in JACKS:
        y = 0.0 if side == "top" else CI_H
        lip = lip.cut(cq.Workplane("XY").workplane(offset=Z_TOP - 2).center(*P(x, y)).rect(JACK_W + 0.4, 8).extrude(2))
    body = body.union(lip)
    # tongues closing the RJ12 openings above the jacks
    for (x, side) in JACKS:
        yc = WALL / 2 if side == "top" else CI_H - WALL / 2
        body = body.union(cq.Workplane("XY").workplane(offset=Z_TOP).center(*P(x, yc)).rect(JACK_W - 0.4, WALL)
                          .extrude(-(TOP_CLR - 0.2)))  # stops 0.2 mm above the jack
    # corner pillars (they replace the tray's wall there) with a LEGO Technic hole, like the CoreInk's back
    outline = slab(CI_W, CI_H, CI_R, Z_CORNER, Z_LID)
    for (x, y) in LEGO_HOLES:
        body = body.union(corner_box(x, y, Z_CORNER, Z_LID).intersect(outline))
    for (x, y) in LEGO_HOLES:
        body = body.cut(technic_hole(x, y))
    # cut-out for the raised bus socket, whose top is flush with the lid (VERIFY against the chosen part)
    body = body.cut(cq.Workplane("XY").workplane(offset=Z_TOP - 2).center(*P(*BUS)).rect(BUS_W + 0.5, BUS_H + 0.5)
                    .extrude(LID_T + 3))
    # orientation mark on the outside: arrow pointing to the meter edge (top), between the two top LEGO holes
    body = body.cut(cq.Workplane("XY").workplane(offset=Z_LID - 0.4).center(*P(CI_W / 2, 4.0))
                    .transformed(rotate=(0, 0, 90)).polygon(3, 3.0).extrude(0.5))
    return body


def main():
    os.makedirs(OUT, exist_ok=True)
    k, l = kuip(), lid()
    for name, part in (("p1-base-kuip", k), ("p1-base-lid", l)):
        cq.exporters.export(part, os.path.join(OUT, name + ".step"))
        cq.exporters.export(part, os.path.join(OUT, name + ".stl"), tolerance=0.02, angularTolerance=0.1)
        print("wrote", name)
    print(f"thickness for shipping (lid top to post tips): {SHIP_T:.1f} mm (max. {SHIP_MAX} mm)")


if __name__ == "__main__":
    main()
