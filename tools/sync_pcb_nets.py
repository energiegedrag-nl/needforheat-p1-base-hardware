"""Rename the nets in the board to the names the schematic gives them, without touching the copper.

Nets are matched by their set of pads, so only names change (for example when a label becomes a
power symbol: "/GND" -> "GND"). Any net whose pads differ is reported and the board is left alone.
Afterwards run DRC with schematic parity.  Run with any Python 3:  python tools/sync_pcb_nets.py
"""
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import parse, find, first  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "needforheat-p1-base-hardware"
PCB = os.path.join(ROOT, "pcb", NAME + ".kicad_pcb")
SCH = os.path.join(ROOT, "pcb", NAME + ".kicad_sch")
CLI = os.environ.get("KICAD_CLI", os.path.expandvars(r"%LOCALAPPDATA%\Programs\KiCad\10.0\bin\kicad-cli.exe"))


def sch_nets():
    with tempfile.TemporaryDirectory() as tmp:
        f = os.path.join(tmp, "n.net")
        subprocess.run([CLI, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", f, SCH], check=True,
                       capture_output=True)
        n = parse(open(f, encoding="utf8").read())
    return {first(nt, "name")[1]: frozenset((first(x, "ref")[1], first(x, "pin")[1]) for x in find(nt, "node"))
            for nt in find(first(n, "nets"), "net")}


def pcb_nets(text):
    b = parse(text)
    nets = {}
    for fp in find(b, "footprint"):
        ref = next(p[2] for p in find(fp, "property") if p[1] == "Reference")
        for pad in find(fp, "pad"):
            net = first(pad, "net")
            if net and pad[1]:
                nets.setdefault(net[-1], set()).add((ref, pad[1]))
    return {k: frozenset(v) for k, v in nets.items()}


def main():
    text = open(PCB, encoding="utf8").read()
    want = {nodes: name for name, nodes in sch_nets().items()}
    rename, problems = {}, []
    for name, nodes in pcb_nets(text).items():
        if nodes not in want:
            problems.append(f"{name}: pads {sorted(nodes)} form no net in the schematic")
        elif want[nodes] != name:
            rename[name] = want[nodes]
    if problems:
        raise SystemExit("board and schematic differ in connectivity, not only in names:\n  " + "\n  ".join(problems))
    for old, new in rename.items():
        text = re.sub(r'\(net "%s"\)' % re.escape(old), '(net "%s")' % new.replace("\\", "\\\\"), text)
        print(f"{old} -> {new}")
    with open(PCB, "w", encoding="utf8", newline="\n") as f:
        f.write(text)
    print(f"{len(rename)} nets renamed")


if __name__ == "__main__":
    main()
