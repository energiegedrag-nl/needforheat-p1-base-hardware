"""Generate simple 3D models (STEP) for parts that have no model in the KiCad library.

- RJ12 (6P6C) right-angle jack for the Connector_RJ:RJ25_Wayconn_MJEA-660X1_Horizontal
  footprint (KiCad ships the footprint but no model). Envelope of the CONNFLY
  DS1133-S60BPX (C77859) from LCSC data: 14.6 x 13 x 14.5 mm.
- 2x8 2.54 mm stacking female header (C72555): 8.5 mm body above the board, long
  pins through the board into the CoreInk socket.

Models are approximations meant for renders and enclosure fit checks, not for
mechanical sign-off. Origin = footprint origin, z = 0 at the top of the board. Shapes are drawn in
footprint coordinates (y down) and mirrored, because KiCad model y points up.

Needs CadQuery:  python tools/gen_3d_models.py
"""
import os

import cadquery as cq

OUT = os.path.join(os.path.dirname(__file__), "..", "pcb", "p1base.3dshapes")

BEIGE = cq.Color(0.86, 0.84, 0.78)
BLACK = cq.Color(0.10, 0.10, 0.10)
GOLD = cq.Color(0.85, 0.70, 0.25)
METAL = cq.Color(0.75, 0.75, 0.72)


def rj12():
    x0, x1, y0, y1, h = -9.85, 4.75, -2.18, 10.82, 14.5
    body = cq.Workplane("XY").box(x1 - x0, y1 - y0, h, centered=False).translate((x0, y0, 0))
    # plug opening on the board-edge face (+y), with the latch slot
    cx = -2.55
    hole = cq.Workplane("XY").box(6.9, 9.0, 7.2, centered=(True, False, False)).translate((cx, y1 - 9.0, 3.0))
    latch = cq.Workplane("XY").box(3.4, 9.0, 1.6, centered=(True, False, False)).translate((cx, y1 - 9.0, 1.6))
    body = body.cut(hole).cut(latch)
    asm = cq.Assembly(name="RJ12")
    asm.add(body.mirror("XZ"), name="body", color=BEIGE)
    # six contacts inside the opening and their PCB legs
    contacts = cq.Workplane("XY")
    legs = cq.Workplane("XY")
    for i in range(6):
        x = -i * 1.02
        y = 0.0 if i % 2 == 0 else 2.54
        contacts = contacts.union(
            cq.Workplane("XY").box(0.35, 5.0, 0.3, centered=(True, False, False)).translate((cx - 2.55 + 1.02 * i + 0.0, y1 - 8.5, 9.4)))
        legs = legs.union(cq.Workplane("XY").box(0.4, 0.4, 4.6).translate((x, y, -0.7)))
    asm.add(contacts.mirror("XZ"), name="contacts", color=GOLD)
    asm.add(legs.mirror("XZ"), name="legs", color=METAL)
    # two plastic locating posts
    posts = (cq.Workplane("XY").pushPoints([(-8.55, 4.84), (3.45, 4.84)]).circle(1.55).extrude(-2.9))
    asm.add(posts.mirror("XZ"), name="posts", color=BEIGE)
    return asm


def stacking_header():
    p, rows, cols, h = 2.54, 8, 2, 8.5
    body = cq.Workplane("XY").box(cols * p, rows * p, h, centered=(True, True, False))
    holes = (cq.Workplane("XY").pushPoints([((c - 0.5) * p, (r - 3.5) * p) for c in range(cols) for r in range(rows)])
             .rect(1.0, 1.0).extrude(h).translate((0, 0, 0.0)))
    body = body.cut(holes.translate((0, 0, 1.5)))
    pins = (cq.Workplane("XY").pushPoints([((c - 0.5) * p, (r - 3.5) * p) for c in range(cols) for r in range(rows)])
            .rect(0.64, 0.64).extrude(-(1.6 + 9.5)).translate((0, 0, 1.5)))
    asm = cq.Assembly(name="StackingHeader_2x08")
    asm.add(body, name="body", color=BLACK)
    asm.add(pins, name="pins", color=GOLD)
    return asm


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, asm in (("RJ12_6P6C_Horizontal_approx", rj12()),
                      ("StackingHeader_2x08_P2.54mm_approx", stacking_header())):
        path = os.path.join(OUT, name + ".step")
        asm.save(path, exportType="STEP")
        print("wrote", os.path.normpath(path))


if __name__ == "__main__":
    main()
