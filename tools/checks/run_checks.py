"""Run the independent design checks and write the reports to docs/checks/.

  1  check_lcsc_pinout   JLCPCB's own (LCSC) footprints, placed with our CPL, land pad-for-pad on ours
  2  check_absmax        worst-case voltage on every net vs the absolute maximum of every pin
  4  check_gerber_netlist connectivity rebuilt from the gerbers alone equals the schematic netlist
  5  check_3d_fit        CoreInk + populated board + tray + lid + RJ12 plugs: collisions and pin engagement

(Check 3, SPICE with tolerances, lives in tools/sim/.)
Run with a Python that has easyeda2kicad, gerbonara, shapely and cadquery:  python tools/checks/run_checks.py
Checks 1 and 2 run in KiCad's own Python (pcbnew); set KICAD_BIN if KiCad is not in the default place.
Check 1 downloads the LCSC CAD data of the BOM parts (only LCSC part numbers are sent) into tools/checks/.cache/.
"""
import os
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
NAME = "needforheat-p1-base-hardware"
PCB = os.path.join(ROOT, "pcb", NAME + ".kicad_pcb")
SCH = os.path.join(ROOT, "pcb", NAME + ".kicad_sch")
JLC = os.path.join(ROOT, "pcb", "jlcpcb")
CACHE = os.path.join(HERE, ".cache")
OUT = os.path.join(ROOT, "docs", "checks")
KICAD_BIN = os.environ.get("KICAD_BIN", os.path.expandvars(r"%LOCALAPPDATA%\Programs\KiCad\10.0\bin"))
KPY = os.path.join(KICAD_BIN, "python.exe")
KCLI = os.path.join(KICAD_BIN, "kicad-cli.exe")


def run(py, script, *args, report=None):
    r = subprocess.run([py, "-W", "ignore", os.path.join(HERE, script), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode:
        raise SystemExit(f"{script} failed:\n{r.stdout}\n{r.stderr}")
    if report:
        with open(os.path.join(OUT, report), "w", encoding="utf-8", newline="\n") as f:
            f.write(r.stdout)
        tail = [l for l in r.stdout.splitlines() if l.strip()][-3:]
        print(f"--- {report}\n" + "\n".join(tail))
    return r.stdout


def main():
    os.makedirs(CACHE, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    parts = os.path.join(CACHE, "lcsc_parts.json")
    run(sys.executable, "lcsc_fetch.py", os.path.join(JLC, f"BOM-{NAME}.csv"), os.path.join(CACHE, "lcsc"), parts)
    run(KPY, "check_lcsc_pinout.py", PCB, os.path.join(JLC, f"CPL-{NAME}.csv"), parts, report="1-lcsc-pinout.txt")
    run(KPY, "check_absmax.py", PCB, report="2-absmax.txt")
    net = os.path.join(CACHE, "sch.net")
    subprocess.run([KCLI, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", net, SCH], check=True,
                   capture_output=True)
    pads = os.path.join(CACHE, "pads.json")
    run(KPY, "board_export.py", PCB, pads)
    gdir = os.path.join(CACHE, "gerber")
    os.makedirs(gdir, exist_ok=True)
    with zipfile.ZipFile(os.path.join(JLC, f"GERBER-{NAME}.zip")) as z:
        z.extractall(gdir)
    run(sys.executable, "check_gerber_netlist.py", gdir, pads, net, report="4-gerber-netlist.txt")
    run(sys.executable, "check_3d_fit.py", ROOT, report="5-3d-fit.txt")


if __name__ == "__main__":
    main()
