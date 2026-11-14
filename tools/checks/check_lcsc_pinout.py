"""Check 1 (KiCad Python): place every LCSC footprint the way JLCPCB does (CPL position and rotation) and test
that each LCSC pad lands on its own KiCad pad. Lists LCSC pin function -> our pad, pin and net for review.
Usage: python check_lcsc_pinout.py <board> <CPL.csv> <lcsc_parts.json>"""
import csv, json, math, sys
import pcbnew

board, cplf, partsf = sys.argv[1:4]
parts = json.load(open(partsf))
b = pcbnew.LoadBoard(board); M = pcbnew.ToMM
cpl = {r["Designator"]: r for r in csv.DictReader(open(cplf, encoding="utf8"))}
problems, shown = [], {}
for fp in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
    ref = fp.GetReference()
    lc = fp.GetFieldText("LCSC") if fp.HasField("LCSC") else ""
    if not lc or ref not in cpl:
        continue
    r = cpl[ref]
    X, Y, a = float(r["Mid X"][:-2]), -float(r["Mid Y"][:-2]), math.radians(float(r["Rotation"]))
    P = parts[lc]
    rows, used = [], {}
    for num, lst in P["pads"].items():
        for (x, y, w, h, rot, shape, drill) in lst:
            bx, by = X + x * math.cos(a) + y * math.sin(a), Y - x * math.sin(a) + y * math.cos(a)
            hit = [pd for pd in fp.Pads() if pd.GetNumber() and pd.HitTest(pcbnew.VECTOR2I(pcbnew.FromMM(bx), pcbnew.FromMM(by)))]
            if len(hit) != 1:
                problems.append(f"{ref} ({lc}) LCSC pad {num}: lands on {len(hit)} KiCad pads")
                continue
            k = hit[0]
            if k.GetNumber() in used and used[k.GetNumber()] != num:
                problems.append(f"{ref} ({lc}) LCSC pads {used[k.GetNumber()]} and {num} land on the same KiCad pad {k.GetNumber()}")
            used[k.GetNumber()] = num
            rows.append((num, P["pins"].get(num, "-"), k.GetNumber(), k.GetPinFunction(), k.GetNetname().lstrip("/")))
    key = (lc, tuple(sorted((n, f, kn) for n, f, kn, _, _ in rows)))
    if key in shown:
        print(f"{ref:5s} {lc:9s} same mapping as {shown[key]}")
        continue
    shown[key] = ref
    print(f"\n{ref} {fp.GetValue()} {lc} ('{P['name']}', LCSC footprint {P['fp']}, CPL rotation {r['Rotation']})")
    for num, func, kn, kf, net in sorted(rows, key=lambda t: (len(t[0]), t[0])):
        print(f"   LCSC {num:>3s} {func:8s} -> pad {kn:>5s} {kf:12s} {net}")
print("\nRESULT:", "every LCSC pad lands on exactly one, distinct KiCad pad" if not problems else "\n  ".join([""] + problems))
