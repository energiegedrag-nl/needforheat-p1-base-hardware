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
YW = K.CLR + K.WALL / 2  # centre of the top wall (CadQuery y is up, so the top wall is at +YW)
YB = -(K.CI_H + K.CLR + K.WALL / 2)  # centre of the bottom wall
XL, XR = -(K.CLR + K.WALL / 2), K.CI_W + K.CLR + K.WALL / 2  # centres of the long walls
LED_MID = sorted(K.LEDS)[len(K.LEDS) // 2] if K.LEDS else (8.2, 1.2)
ZLED = K.GAP + K.PCB_T + K.LED_LENS_Z

# (anchor x, y, z in CadQuery coordinates, label); y = -board y
VIEWS = [
    ("tray-top-edge", "p1-base-kuip.stl", 28, 62, [
        ((20.0, YW, 10.0), "RJ12 opening for J2 (smart meter); the lid's tongue closes it above the jack"),
        ((LED_MID[0], YW + 0.8, ZLED), "Light windows for the three side-looking LEDs\n(red, yellow, green, from left to right)"),
        ((XL + 0.9, -K.SNAP_Y[0], ZT - K.LIP_H / 2), "Snap-fit groove (2 per long wall) for the lid's bumps"),
        ((4.0, -4.0, K.GAP + K.PCB_T - 0.2), "Peg in a corner block: keys and holds the PCB;\nthe block carries it 2.5 mm above the CoreInk"),
        ((36.0, -52.0, K.GAP), "4th corner without a peg: the PCB fits one way only"),
        ((20.0, YW + 0.9, -1.6), "Skirt cut-out for the CoreInk's HAT connector"),
        ((32.0, YB, ZT - 0.3), "Pry notch: lift the lid here"),
    ]),
    ("tray-underside", "p1-base-kuip.stl", -32, -60, [
        ((4.0, -52.0, -4.0), "LEGO-compatible post (4x, 7 mm, three crush ribs):\nlocates the tray in the CoreInk's LEGO holes"),
        ((20.0, YB - 0.9, 10.0), "RJ12 opening for J3 (existing P1 reader)"),
        ((18.0, YB + 0.9, -1.6), "Skirt cut-out for the CoreInk's USB-C and Grove ports"),
        ((XL - 0.9, -19.5, -1.6), "Skirt cut-outs for the dial and the power switch"),
        ((XR, -30.0, -2.0), "Skirt: the wall continues 3 mm down over the CoreInk"),
    ]),
    ("lid-underside", "p1-base-lid.stl", -40, 62, [
        ((XL + 1.3, -K.SNAP_Y[0], ZT - K.LIP_H / 2), "Snap bump on the flexible lip (2 per long side)"),
        ((20.0, YW, ZT - 0.3), "Tongue that closes the RJ12 opening above J2\n(same above J3)"),
        ((4.0, -4.0, ZT + K.LID_T - K.POST_L - 0.5), "LEGO tube (4x): holes at the CoreInk's positions,\nfor the next module's posts"),
        ((K.BUS[0], -K.BUS[1], ZT), "Cut-out for the raised bus socket J1,\nflush with the lid like the CoreInk's back"),
        ((20.0, YW - 1.0, ZT - 1.0), "Lip notch above the RJ12 jacks"),
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
             "lid-underside": "Lid, seen from below (inside)"}[name]
    fig.text(0.5, 0.97, title, ha="center", va="top", fontsize=14, weight="bold")
    out = os.path.join(IMG, f"enclosure-{name}-callouts.png")
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def main():
    os.makedirs(IMG, exist_ok=True)
    for v in VIEWS:
        draw(*v)


if __name__ == "__main__":
    main()
