"""Generate simple 3D models (STEP) for parts that have no model in the KiCad library.

- RJ12 (6P6C) right-angle jack for the Connector_RJ:RJ25_Wayconn_MJEA-660X1_Horizontal
  footprint (KiCad ships the footprint but no model). Envelope of the CONNFLY
  DS1133-S60BPX (C77859) from LCSC data: 14.6 x 13 x 14.5 mm.
- 2x8 2.54 mm elevated socket (Samtec ESQ-108-24-G-D): 13.59 mm body standing on the board, long
  pins through the board into the CoreInk socket.
- Lite-On LTST-S220 side-looking LED (the three indicator LEDs at the top edge).

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


def rj12_5301():
    """EVERCOM 5301-6P6C (C3097716): 18.05 x 13.3 mm, 11.45 mm high, plug opening at x = -15.62 (footprint frame).
    EVERCOM drawing 5301-660XXX rev. A (2025-09-23, chinarj45.com; no 3D model is published): leads Ø0.46, 3.0 mm
    below the seating plane; two snap-in posts for Ø3.2 holes, 10.16 mm apart, 8.00 mm behind the front face; posts
    3.6 mm long (LCSC 3D model)."""
    x0, x1, y0, y1, h = -15.62, 2.43, -6.65, 6.65, 11.45
    # plug cavity: 6P6C plug 9.65 x 6.6 mm (check 5 inserts one with its centre 6.6 mm above the board), latch down
    cav_w, cav_z0, cav_z1, cav_d = 9.9, 3.2, 10.0, 13.0
    slot_w, slot_z0 = 3.9, 0.9
    body = (cq.Workplane("XY").box(x1 - x0, y1 - y0, h, centered=False).translate((x0, y0, 0))
            .edges("|Z").chamfer(0.3).faces(">Z").edges().chamfer(0.3))
    # underside: shallow recess, the body stands on a 1.2 mm rim
    body = body.cut(cq.Workplane("XY").box(x1 - x0 - 2.4, y1 - y0 - 2.4, 0.3, centered=False)
                    .translate((x0 + 1.2, y0 + 1.2, -0.01)))
    cavity = cq.Workplane("XY").box(cav_d, cav_w, cav_z1 - cav_z0, centered=(False, True, False)).translate((x0 - 0.01, 0, cav_z0))
    slot = cq.Workplane("XY").box(cav_d, slot_w, cav_z0 - slot_z0 + 0.01, centered=(False, True, False)).translate((x0 - 0.01, 0, slot_z0))
    # lead-in: the opening widens 0.4 mm over the first 0.6 mm
    lead_in = (cq.Workplane("YZ", origin=(x0 - 0.01, 0, 0)).center(0, (cav_z0 + cav_z1) / 2).rect(cav_w + 0.8, cav_z1 - cav_z0 + 0.8)
               .workplane(offset=0.6).rect(cav_w, cav_z1 - cav_z0).loft())
    body = body.cut(cavity).cut(slot).cut(lead_in)
    # comb between the contacts at the back of the cavity ceiling (the contacts run in its slots)
    comb = cq.Workplane("XY")
    for i in range(7):
        y = (i - 3) * 1.02
        comb = comb.union(cq.Workplane("XY").box(4.0, 0.4, 1.2, centered=(False, True, False))
                          .translate((x0 + cav_d - 4.0, y, cav_z1 - 1.2)))
    body = body.union(comb.intersect(cavity))
    asm = cq.Assembly(name="RJ12_5301")
    asm.add(body.mirror("XZ"), name="body", color=BEIGE)
    # six spring contacts (Ø0.46, 1.02 mm pitch): from the cavity ceiling at the back, sloping down towards the
    # opening (relaxed position; a plug pushes them up), then down through the body to the round leads
    pins = [(1.27, -3.18), (-1.27, -1.91), (1.27, -0.64), (-1.27, 0.63), (1.27, 1.90), (-1.27, 3.17)]
    contacts = cq.Workplane("XY")
    r = 0.23
    for i, (px, py) in enumerate(pins):
        yc = (i - 2.5) * 1.02
        a = cq.Vector(x0 + cav_d - 0.5, yc, cav_z1 - 0.3)
        b = cq.Vector(x0 + 4.0, yc, cav_z1 - 2.0)
        for p, q in ((a, b), (cq.Vector(px, py, -3.0), cq.Vector(px, py, 1.0))):
            d = q - p
            contacts = contacts.union(cq.Workplane("XY").add(cq.Solid.makeCylinder(r, d.Length, p, d.normalized())))
        contacts = contacts.union(cq.Workplane("XY").add(cq.Solid.makeSphere(r, b)))
    asm.add(contacts.mirror("XZ"), name="contacts", color=GOLD)
    # two split snap-in posts for the Ø3.2 holes: barb near the tip, slit across
    posts = cq.Workplane("XY")
    for py in (5.08, -5.08):
        shank = cq.Workplane("XY").center(-7.62, py).circle(1.45).extrude(-3.6)
        barb = (cq.Workplane("XY").workplane(offset=-2.6).center(-7.62, py).circle(1.75)
                .workplane(offset=-0.7).circle(1.2).loft())
        slit = cq.Workplane("XY").box(0.7, 4.0, 3.0, centered=(True, True, False)).translate((-7.62, py, -3.7))
        posts = posts.union(shank.union(barb).cut(slit))
    asm.add(posts.mirror("XZ"), name="posts", color=BEIGE)
    return asm


def side_led():
    """Lite-On LTST-S220 side-looking LED: about 2.2 x 1.0 x 0.9 mm, lens on the -y face (VERIFY)."""
    body = cq.Workplane("XY").box(2.2, 1.0, 0.9, centered=(True, True, False))
    lens = cq.Workplane("XY").box(1.2, 0.1, 0.6, centered=(True, True, False)).translate((0, -0.5, 0.15))
    ends = cq.Workplane("XY").pushPoints([(-1.0, 0), (1.0, 0)]).box(0.25, 1.02, 0.92, centered=(True, True, False))
    asm = cq.Assembly(name="LTST_S220")
    asm.add(body.cut(lens).mirror("XZ"), name="body", color=cq.Color(0.95, 0.95, 0.92))
    asm.add(lens.mirror("XZ"), name="lens", color=cq.Color(0.85, 0.9, 1.0))
    asm.add(ends.mirror("XZ"), name="terminals", color=METAL)
    return asm


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, asm in (("RJ12_6P6C_Horizontal_approx", rj12()), ("RJ12_EVERCOM_5301_approx", rj12_5301()),
                      ("LED_LiteOn_LTST-S220_approx", side_led())):
        path = os.path.join(OUT, name + ".step")
        asm.save(path, exportType="STEP")
        print("wrote", os.path.normpath(path))


if __name__ == "__main__":
    main()
