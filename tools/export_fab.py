"""Export fabrication files (JLCPCB), PDF printouts and renders with kicad-cli.

Run with any Python 3:  python tools/export_fab.py
Set KICAD_CLI if kicad-cli is not in the default location.
"""
import csv
import math
import os
import subprocess
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCBDIR = os.path.join(ROOT, "pcb")
NAME = "needforheat-p1-base-hardware"
PCB = os.path.join(PCBDIR, NAME + ".kicad_pcb")
SCH = os.path.join(PCBDIR, NAME + ".kicad_sch")
JLC = os.path.join(PCBDIR, "jlcpcb")
DOCS = os.path.join(ROOT, "docs")
IMG = os.path.join(DOCS, "images")
CLI = os.environ.get("KICAD_CLI", os.path.expandvars(r"%LOCALAPPDATA%\Programs\KiCad\10.0\bin\kicad-cli.exe"))

# JLCPCB places parts with the LCSC footprints, whose origin and base rotation can
# differ from the KiCad footprint: (dx, dy) = LCSC origin in KiCad footprint
# coordinates (mm, y down), drot = rotation to add (degrees, counter-clockwise).
# Checked in the JLCPCB placement preview (November 2026).
JLC_CORR = {
    # CONNFLY DS1133-S60BPX (C77859): origin at the centre of the six pins, opening towards -x
    "RJ25_Wayconn_MJEA-660X1_Horizontal": (-2.55, 1.27, 90.0),
    # C72555: pins along x in the LCSC footprint, along y in ours
    "CoreInk_Bus_2x08_P2.54mm": (0.0, 0.0, 90.0),
    # pin 1 on the opposite side / a quarter turn in the JLCPCB library
    "SOT-23": (0.0, 0.0, 180.0),
    "SOT-23-5": (0.0, 0.0, 180.0),
    "SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm": (0.0, 0.0, 270.0),
}

LAYERS = "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"


def cli(*args):
    r = subprocess.run([CLI, *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit(f"kicad-cli {' '.join(args)} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout


def gerbers():
    with tempfile.TemporaryDirectory() as tmp:
        cli("pcb", "export", "gerbers", "--layers", LAYERS, "--subtract-soldermask", "-o", tmp + os.sep, PCB)
        cli("pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th", "--drill-origin", "absolute",
            "--excellon-units", "mm", "-o", tmp + os.sep, PCB)
        out = os.path.join(JLC, f"GERBER-{NAME}.zip")
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(os.listdir(tmp)):
                z.write(os.path.join(tmp, f), f)
    print("wrote", out)


def bom():
    with tempfile.TemporaryDirectory() as tmp:
        f = os.path.join(tmp, "bom.csv")
        cli("sch", "export", "bom", "--fields", "Value,Reference,Footprint,LCSC,${QUANTITY},${DNP}",
            "--labels", "Value,Reference,Footprint,LCSC,Qty,DNP", "--group-by", "Value,Footprint,LCSC",
            "--exclude-dnp", "--ref-range-delimiter", "", "-o", f, SCH)
        rows = list(csv.DictReader(open(f, encoding="utf-8")))
    out = os.path.join(JLC, f"BOM-{NAME}.csv")
    with open(out, "w", newline="", encoding="utf-8") as fo:
        w = csv.writer(fo)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC"])
        merged = {}  # one line per LCSC part (JLC warns about duplicate lines)
        for r in rows:
            if not r["LCSC"]:
                continue  # test points, peg holes
            m = merged.setdefault(r["LCSC"], [[], [], r["Footprint"].split(":")[-1]])
            m[0].append(r["Value"])
            m[1].extend(r["Reference"].split(","))
        for lcsc, (values, refs, fp) in merged.items():
            w.writerow([" / ".join(dict.fromkeys(values)), ",".join(refs), fp, lcsc])
    print("wrote", out)


def cpl():
    with tempfile.TemporaryDirectory() as tmp:
        f = os.path.join(tmp, "pos.csv")
        cli("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "front", "--exclude-dnp",
            "--use-drill-file-origin", "-o", f, PCB)
        rows = list(csv.DictReader(open(f, encoding="utf-8")))
    out = os.path.join(JLC, f"CPL-{NAME}.csv")
    with open(out, "w", newline="", encoding="utf-8") as fo:
        w = csv.writer(fo)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for r in rows:
            if r["Ref"].startswith(("TP", "H")):
                continue
            x, y, rot = float(r["PosX"]), float(r["PosY"]), float(r["Rot"])
            dx, dy, drot = JLC_CORR.get(r["Package"], (0.0, 0.0, 0.0))
            a = math.radians(rot)
            # offset is in footprint coordinates (y down); the pos file has y up
            x += dx * math.cos(a) + dy * math.sin(a)
            y -= -dx * math.sin(a) + dy * math.cos(a)
            w.writerow([r["Ref"], f"{x:.4f}mm", f"{y:.4f}mm", "Top", f"{(rot + drot) % 360:.1f}"])
    print("wrote", out)


def pdfs():
    cli("sch", "export", "pdf", "-o", os.path.join(DOCS, f"{NAME}-sch.pdf"), SCH)
    cli("pcb", "export", "pdf", "--layers", "F.Cu,F.Silkscreen,F.Fab,Edge.Cuts", "--mode-single",
        "-o", os.path.join(DOCS, f"{NAME}-pcb.pdf"), PCB)
    cli("pcb", "export", "pdf", "--layers", "B.Cu,B.Silkscreen,Edge.Cuts", "--mode-single", "--mirror",
        "-o", os.path.join(DOCS, f"{NAME}-pcb-bottom.pdf"), PCB)
    print("wrote PDFs")


def renders():
    os.makedirs(IMG, exist_ok=True)
    cli("pcb", "render", "--side", "top", "--width", "1000", "--height", "1300", "--quality", "high",
        "-o", os.path.join(IMG, "p1-base-v3-top.png"), PCB)
    cli("pcb", "render", "--side", "bottom", "--width", "1000", "--height", "1300", "--quality", "high",
        "-o", os.path.join(IMG, "p1-base-v3-bottom.png"), PCB)
    cli("pcb", "render", "--rotate", "-45,0,30", "--width", "1400", "--height", "1000", "--quality", "high",
        "--zoom", "0.9", "-o", os.path.join(IMG, "p1-base-v3-3d.png"), PCB)
    cli("pcb", "render", "--side", "front", "--width", "1400", "--height", "700", "--quality", "high",
        "--zoom", "1.2", "-o", os.path.join(IMG, "p1-base-v3-side.png"), PCB)
    cli("pcb", "export", "step", "--subst-models", "--force", "-o", os.path.join(ROOT, "enclosure", "p1-base-v3-pcb.step"), PCB)
    print("wrote renders and STEP")


if __name__ == "__main__":
    os.makedirs(JLC, exist_ok=True)
    for f in os.listdir(JLC):
        os.remove(os.path.join(JLC, f))
    gerbers()
    bom()
    cpl()
    pdfs()
    renders()
