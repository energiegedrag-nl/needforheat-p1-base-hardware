"""Renders of the P1-BASE v3 enclosure with numbered callouts that say what each cut-out or feature is for.

Run with the same Python as kuip.py (CadQuery, plus matplotlib and trimesh), after kuip.py:
    python enclosure/callouts.py
Writes docs/images/enclosure-*-callouts.png. The callout positions come from the parameters in kuip.py (and
pcb_features.json), so they follow the design when it changes.
"""
import os
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from mpl_toolkits.mplot3d import proj3d
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

import kuip as K

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(os.path.dirname(HERE), "docs", "images")

ZT = K.Z_TOP
YW = -K.WALL / 2  # centre of the top wall (CadQuery y = -board y; the outside is the CoreInk outline)
YB = -(K.CI_H - K.WALL / 2)  # centre of the bottom wall
XL, XR = K.WALL / 2, K.CI_W - K.WALL / 2  # centres of the long walls
LED_TOP = min(K.LEDS, key=lambda p: p[1]) if K.LEDS else (11.7, 3.05)  # LED1, next to J2
LED_BOT = max(K.LEDS, key=lambda p: p[1]) if K.LEDS else (28.3, 52.95)  # LED2, next to J3
ZLED = K.GAP + K.PCB_T + K.LED_LENS_Z
ZL = K.Z_LID
ZSILL = K.GAP + K.PCB_T - 0.3  # bottom edge of the RJ12 openings

# (anchor x, y, z in CadQuery coordinates, label); y = -board y
VIEWS = [
    ("tray-top-edge", "p1-base-kuip.stl", 28, 62, [
        ((K.JACKS[0][0], YW, ZSILL), "RJ12 opening for J2 (smart meter); the lid's tongue closes it above the jack"),
        ((LED_TOP[0], YW, ZLED), "Light window for LED1 (green, side-looking), open into\nthe J2 opening: blinks with the data from the meter"),
        ((XL + 0.5, -K.SNAP_Y[0], ZT - K.LIP_H / 2), "Snap-fit groove (2 per long wall) for the lid's bumps"),
        ((36.0, -4.0, K.GAP + K.PCB_T - 0.2), "Peg in a corner block: keys and holds the PCB;\nthe block carries it 2.5 mm above the CoreInk"),
        ((4.0, -4.0, K.GAP), "Corner block without a peg:\nthe PCB fits one way only"),
        ((36.0, -1.0, K.Z_CORNER), "Corner notch: the lid's corner pillar fills it"),
        ((K.CORNER + K.KEY_L / 2, YW, K.Z_CORNER), "Key: only this corner is cut 2.5 mm further along\nboth walls, so the lid fits one way only"),
    ]),
    ("tray-underside", "p1-base-kuip.stl", -32, -60, [
        ((4.0, -52.0, -4.0), "LEGO-compatible post (4x, 7 mm, three crush ribs):\nlocates the tray in the CoreInk's LEGO holes"),
        ((K.JACKS[1][0], YB, ZSILL), "RJ12 opening for J3 (existing P1 reader)"),
        ((LED_BOT[0], YB, ZLED), "Light window for LED2 (green, side-looking):\nblinks while the existing reader gets data"),
        ((K.PRY_X, YB, ZT - K.PRY_D), "Pry notch: lift the lid here with a fingernail\nor a small screwdriver"),
        ((XR, -30.0, 1.0), "Outside flush with the CoreInk (40 x 56 mm, R3), no skirt:\nany CoreInk BASE also fits behind this module"),
        ((36.0, -52.0, K.GAP / 2), "Corner block: the PCB rests on it"),
    ]),
    ("lid-underside", "p1-base-lid.stl", -40, 62, [
        ((XL + 1.6, -K.SNAP_Y[0], ZT - K.LIP_H / 2), "Snap bump on the flexible lip (2 per long side)"),
        ((20.0, YW, ZT - 0.3), "Tongue that closes the RJ12 opening above J2\n(same above J3)"),
        ((K.CORNER + K.KEY_L / 2, YW, K.Z_CORNER), "Key: this corner pillar is an L, 2.5 mm longer along\nboth walls; turned round it stops on the tray's wall"),
        ((36.0, -6.0, K.GAP + K.PCB_T + K.FOOT_GAP), "Foot (3x, not at the key corner): holds the PCB\ndown, 0.1 mm above it"),
        ((36.0, -4.0, K.Z_CORNER), "Corner pillar (4x) with a LEGO Technic hole at the\nCoreInk's position: counterbore, bore and snap groove,\nso a Technic pin clicks in; also takes the next module's posts"),
        ((K.BUS[0], -K.BUS[1], ZT), "Cut-out for the raised bus socket J1 (0.4 mm around it);\nthe socket top sits 0.3 mm below the lid's surface"),
        ((20.0, -(K.CI_H - K.WALL - 1.0), ZT - 1.0), "Lip notch above the RJ12 jacks"),
    ]),
    ("lid-outside", "p1-base-lid.stl", 55, 62, [
        ((20.0, -4.0, ZL), "Arrow: this edge goes to the meter (J2)"),
        ((36.0, -4.0, ZL), "LEGO Technic hole (4x), same positions as on the CoreInk"),
        ((K.BUS[0], -K.BUS[1], ZL), "Bus socket J1 for the next module, 0.3 mm below the lid"),
    ]),
]


def draw(name, stl, elev, azim, callouts):
    m = trimesh.load(os.path.join(HERE, "fabrication", stl))
    tri = m.vertices[m.faces]
    light = np.array([0.4, 0.6, 0.8]) / np.linalg.norm([0.4, 0.6, 0.8])
    shade = 0.45 + 0.55 * np.clip(np.abs(m.face_normals @ light), 0, 1)
    colors = np.c_[np.outer(shade, [0.30, 0.31, 0.34]), np.ones(len(shade))]
    fig = plt.figure(figsize=(13, 8), dpi=120)
    ax = fig.add_axes([0.2, 0.0, 0.6, 0.94], projection="3d")
    ax.add_collection3d(Poly3DCollection(tri, facecolors=colors, edgecolors="none"))
    lo, hi = m.bounds
    c, r = (lo + hi) / 2, (hi - lo).max() / 2 * 0.7  # zoom in: the model fills the middle of the figure
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1)); ax.view_init(elev=elev, azim=azim); ax.set_axis_off()
    fig.canvas.draw()
    pts = []
    for (x, y, z), text in callouts:
        px, py, _ = proj3d.proj_transform(x, y, z, ax.get_proj())
        fx, fy = fig.transFigure.inverted().transform(ax.transData.transform((px, py)))
        pts.append((fx, fy, text))
    # labels left and right of the model, in the order of their anchors' height, so leader lines do not cross
    order = sorted(range(len(pts)), key=lambda i: pts[i][0])
    left, right = order[:(len(order) + 1) // 2], order[(len(order) + 1) // 2:]
    for side, idx in (("left", left), ("right", right)):
        idx = sorted(idx, key=lambda i: -pts[i][1])
        for k, i in enumerate(idx):
            fx, fy, text = pts[i]
            ty = 0.84 - k * (0.68 / max(len(idx) - 1, 1)) if len(idx) > 1 else 0.5
            tx = 0.3 if side == "left" else 0.7
            text = "\n".join(textwrap.fill(t, 32) for t in text.split("\n"))
            fig.add_artist(plt.Line2D([fx, tx], [fy, ty], transform=fig.transFigure, color="#d9480f", lw=1.1))
            fig.add_artist(plt.Circle((fx, fy), 0.004, transform=fig.transFigure, color="#d9480f"))
            fig.text(tx + (-0.005 if side == "left" else 0.005), ty, f"{i + 1}. {text}", fontsize=10.5,
                     ha="right" if side == "left" else "left", va="center",
                     bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#d9480f", lw=0.8))
    title = {"tray-top-edge": "Tray, seen from the top edge (meter side)",
             "tray-underside": "Tray, seen from below (CoreInk side)",
             "lid-underside": "Lid, seen from below (inside)",
             "lid-outside": "Lid, outside (the back of the module)"}[name]
    fig.text(0.5, 0.97, title, ha="center", va="top", fontsize=14, weight="bold")
    out = os.path.join(IMG, f"enclosure-{name}-callouts.png")
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def keying(lift_ok=12.0):
    """Manual picture: the lid goes on one way only. Left: right way round, the L-shaped key pillar above its cut-out.
    Right: turned 180 deg, the key lands on the full wall and the lid stays up (stand-off computed from the solids)."""
    import cadquery as cq
    tray = trimesh.load(os.path.join(HERE, "fabrication", "p1-base-kuip.stl"))
    lid = trimesh.load(os.path.join(HERE, "fabrication", "p1-base-lid.stl"))
    (ax0, ax1, ay0, ay1), (bx0, bx1, by0, by1) = K.KEY_STRIPS

    reach = K.CORNER + K.KEY_L + K.KEY_CLR + 0.05  # the key corner, board frame from (0, 0)

    def in_key(mesh, is_lid):
        """Faces of the L-shaped key pillar (lid) or of the key corner's cut-out (tray); CadQuery y = -board y."""
        c = mesh.triangles_center
        x, y, z = c[:, 0], -c[:, 1], c[:, 2]
        if is_lid:
            return (x <= reach) & (y <= reach) & (z >= K.Z_CORNER - 0.1) & (z <= K.Z_TOP + 0.05)
        return (x <= reach) & (y <= reach) & (z >= K.Z_CORNER - 0.3)

    def landing(mesh):
        """Rim faces of the tray's bottom-right corner, where the turned key lands."""
        c, nz = mesh.triangles_center, mesh.face_normals[:, 2]
        return (c[:, 0] >= K.CI_W - reach) & (-c[:, 1] >= K.CI_H - reach) & (c[:, 2] >= K.Z_TOP - 0.05) & (nz > 0.9)

    # how far the turned lid stays up: from the solids, like check 5
    kt = cq.importers.importStep(os.path.join(HERE, "fabrication", "p1-base-kuip.step"))
    lt = cq.importers.importStep(os.path.join(HERE, "fabrication", "p1-base-lid.step"))
    ctr = cq.Vector(K.CI_W / 2, -K.CI_H / 2, 0)
    lt = lt.rotate(ctr, ctr + cq.Vector(0, 0, 1), 180)
    lo, hi = 0.0, 20.0
    while hi - lo > 0.05:
        m = (lo + hi) / 2
        if kt.intersect(lt.translate((0, 0, m))).val().Volume() > 1e-3:
            lo = m
        else:
            hi = m
    stand = hi

    light = np.array([0.4, 0.6, 0.8]) / np.linalg.norm([0.4, 0.6, 0.8])
    fig = plt.figure(figsize=(14, 7.6), dpi=120)
    panels = [("Right way round: arrow to the meter edge", False, lift_ok, "#2b8a3e"),
              ("Turned round: the lid will not go on", True, stand, "#c92a2a")]
    for n, (title, turned, dz, accent) in enumerate(panels):
        ax = fig.add_axes([0.0 + n * 0.5, 0.06, 0.5, 0.82], projection="3d")
        tris, cols = [], []
        for mesh, is_lid in ((tray, False), (lid, True)):
            v = mesh.vertices.copy()
            key = in_key(mesh, is_lid)
            hit = landing(mesh) if (turned and not is_lid) else np.zeros(len(mesh.faces), bool)
            if is_lid and turned:
                v[:, 0], v[:, 1] = K.CI_W - v[:, 0], -K.CI_H - v[:, 1]
            if is_lid:
                v[:, 2] += dz
            shade = 0.45 + 0.55 * np.clip(np.abs(mesh.face_normals @ light), 0, 1)
            base = np.array([0.42, 0.44, 0.48]) if is_lid else np.array([0.30, 0.31, 0.34])
            hl = np.array(matplotlib.colors.to_rgb("#f08c00"))
            c = np.where(key[:, None], np.outer(shade, hl), np.outer(shade, base))
            c = np.where(hit[:, None], np.outer(shade, matplotlib.colors.to_rgb("#e03131")), c)
            tris.append(v[mesh.faces]); cols.append(np.c_[c, np.ones(len(c))])
        ax.add_collection3d(Poly3DCollection(np.concatenate(tris), facecolors=np.concatenate(cols), edgecolors="none"))
        r = 30
        ax.set_xlim(20 - r, 20 + r); ax.set_ylim(-28 - r, -28 + r); ax.set_zlim(-8, -8 + 2 * r)
        ax.set_box_aspect((1, 1, 1)); ax.view_init(elev=14, azim=-58 if turned else 122)  # each looks at the key
        ax.set_axis_off()
        fig.canvas.draw()

        def at(x, y, z):
            px, py, _ = proj3d.proj_transform(x, y, z, ax.get_proj())
            return fig.transFigure.inverted().transform(ax.transData.transform((px, py)))
        fig.text(0.25 + n * 0.5, 0.93, ("✔ " if not turned else "✘ ") + title, ha="center", va="top",
                 fontsize=14, weight="bold", color=accent)
        if not turned:
            notes = [(at(K.CORNER / 2, -K.WALL / 2, K.Z_CORNER + dz), (0.06, 0.80),
                      "Key: L-shaped corner pillar on the lid (orange)"),
                     (at(K.CORNER + K.KEY_L / 2, -K.WALL / 2, K.Z_TOP), (0.06, 0.20),
                      "...drops into the matching cut-out at the meter-edge\ncorner of the tray (J2 side)")]
            msg = "Hold the arrow on the lid towards the meter edge (J2). The lid slides in and clicks on."
        else:
            cx, cy = K.CI_W - (ax0 + ax1) / 2, -(K.CI_H - K.WALL / 2)
            notes = [(at(cx, cy, K.Z_TOP), (0.58, 0.20),
                      f"The key lands on the wall's rim (red) at the J3 corner:\nthe lid stays {stand:.1f} mm up, the lip never\nenters the tray, nothing clicks")]
            msg = "Felt at the very first touch: turn the lid round."
        for (fx, fy), (tx, ty), text in notes:
            fig.add_artist(plt.Line2D([fx, tx + 0.09], [fy, ty], transform=fig.transFigure, color=accent, lw=1.2))
            fig.add_artist(plt.Circle((fx, fy), 0.005, transform=fig.transFigure, color=accent))
            fig.text(tx, ty, text, fontsize=10.5, va="center",
                     bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=accent, lw=0.9))
        fig.text(0.25 + n * 0.5, 0.04, msg, ha="center", fontsize=11)
    out = os.path.join(IMG, "enclosure-lid-keying.png")
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    print("wrote", out, f"(turned lid stands {stand:.1f} mm up)")


def main():
    os.makedirs(IMG, exist_ok=True)
    for v in VIEWS:
        draw(*v)
    keying()


if __name__ == "__main__":
    main()
