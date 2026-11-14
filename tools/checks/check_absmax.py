"""Check 2 (KiCad Python): worst-case voltage on every net vs the absolute maximum of every pin on that net.
Every connected pin must have a limit in limits(), otherwise it is listed as a coverage gap.
Usage: python check_absmax.py <board>
Limits are datasheet absolute maximum ratings; net voltages are hand-derived worst cases (see NETV)."""
import sys
import pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
VM = 5.5          # DSMR meter 5 V, +10 % worst case
VF_BAT54 = 0.25   # BAT54C forward drop at a few mA (low end -> highest V5)
V5 = VM - VF_BAT54
# ---- worst-case net voltages (min, max) relative to board GND, normal operation incl. any reader on J3 ----
th = lambda v, r1, r2: v * r2 / (r1 + r2)
NETV = {
 "GND": (0, 0), "P1_5V": (0, VM), "VMETER": (0, VM), "V5": (0, V5), "COREINK_5VOUT": (0, 5.25),
 "Q1_G": (0, 0), "G36_VMETER": (0, th(VM, 100e3, 68e3)),
 "P1_DATA_RAW": (0, V5), "P1_DATA": (0, V5), "SPLIT_DRV": (0, V5), "G13_RX": (0, 3.3), "COREINK_3V3": (0, 3.3),
 "EXT_DATA_FET": (0, VM), "EXT_DATA_OUT": (0, VM), "LED1_A": (0, V5),
 "METER_REQ_RAW": (0, VM), "METER_REQ": (0, VM), "REQ_GATE": (0, V5), "REQ_EN": (0, 3.3), "G26_REQ": (0, 3.3),
 "EXT_REQ_RAW": (0, VM), "EXT_REQ": (0, VM), "EXT_REQ_G": (0, th(VM, 10e3, 100e3)),
 "G34_EXTREQ": (0, th(VM, 47e3, 68e3)), "LED2_A": (0, V5),
 "CHG_GATE": (0, VM), "CHG_GATE_DRV": (0, VM), "CHG_EN": (0, 3.3), "G25_CHG": (0, 3.3), "CHG_IN": (0, VM),
 "PROG": (0, 1.0), "PROG_HI": (0, 1.0), "CHG_HI": (0, 3.3), "G14_CHGHI": (0, 3.3), "COREINK_BAT": (0, 4.25),
 "CHRG_N": (0, VM), "LED3_A": (0, VM),
}
# ---- pin limits: (part prefix or value, pad) -> (min, max, note) ----
ESP = (-0.3, 3.6, "ESP32 GPIO, VDD+0.3 at VDD=3.3 (abs max 3.6)")
def limits(fp, pad, net):
    v = fp.GetValue(); ref = fp.GetReference()
    if ref.startswith("R"): return (-50, 50, "0603 resistor")
    if v in ("1u", "100n", "22n"): return (-50, 50, "0603 X5R/X7R 50 V")
    if v == "10u": return (-25, 25, "0805 X5R 25 V")
    if v == "2N7002":   return {"1": (-20, 20, "Vgs"), "2": (0, 0.01, "S"), "3": (-0.5, 60, "Vds")}[pad]
    if v == "AO3401A":  return {"1": (-12, 12, "Vgs (rel. S)"), "2": (-30, 30, "S"), "3": (-30, 30, "Vds")}[pad]
    if v == "74LVC1G14": return {"2": (-0.5, 6.5, "input"), "4": (-0.5, 6.5, "output"), "5": (-0.5, 6.5, "VCC"), "3": (0, 0, "GND"), "1": (-9, 9, "NC")}[pad]
    if v == "TP4056": return {"4": (-0.3, 8, "VCC"), "8": (-0.3, 8, "CE"), "1": (-0.3, 10, "TEMP"), "2": (-0.3, 10, "PROG"),
                              "5": (-0.3, 7, "BAT"), "7": (-0.3, 10, "CHRG#"), "6": (-0.3, 10, "STDBY#"), "3": (0, 0, "GND"), "9": (0, 0, "EP")}[pad]
    if v == "BAT54C": return (-30, 30, "Vr 30 V")
    if v == "1N5819WS": return (-40, 40, "Vr 40 V")
    if v in ("SMF5.0A", "SMF6.0A"): return (-0.5, float(v[3:6]), f"TVS stand-off {v[3:6]} V (leakage rises above)")
    if v == "PESD5V0S1BB": return (-5.0, 5.0, "TVS stand-off +/-5 V")
    if v.startswith("LED"): return (-99, 99, "LED: never reverse biased here (series R from the supply side)")
    if ref == "J1":
        return {"G13": ESP, "G14": ESP, "G25": ESP, "G26": ESP, "G34": ESP, "G36": ESP,
                "BAT": (0, 4.35, "CoreInk battery pin (Li-ion)"), "5VOUT": (0, 5.5, "CoreInk 5V out"), "GND": (0, 0, "GND"),
                "3V3": (0, 3.6, "CoreInk 3.3 V rail")}.get(pad, (-9, 9, "NC"))
    if ref in ("J2", "J3"): return (-30, 30, "RJ12 contact")
    if ref.startswith("TP") or ref.startswith("H"): return (-99, 99, "")
    return None
bad, missing = [], []
for fp in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
    for pd in fp.Pads():
        net = pd.GetNetname().lstrip("/")
        if not net or net.startswith("unconnected"): continue
        lim = limits(fp, pd.GetNumber(), net)
        if lim is None: missing.append(f"{fp.GetReference()}.{pd.GetNumber()}"); continue
        if net not in NETV: missing.append(f"net {net}"); continue
        lo, hi = NETV[net]
        if fp.GetValue() in ("AO3401A",) and pd.GetNumber() == "1":
            continue  # Vgs handled below
        if hi > lim[1] + 1e-9 or lo < lim[0] - 1e-9:
            bad.append(f"{fp.GetReference()}.{pd.GetNumber()} {fp.GetValue()} on {net}: {lo:.2f}..{hi:.2f} V vs {lim[0]}..{lim[1]} V ({lim[2]})")
        elif lim[1] < 10 and hi > 0.95 * lim[1]:
            bad.append(f"(margin <5%) {fp.GetReference()}.{pd.GetNumber()} {fp.GetValue()} on {net}: max {hi:.2f} V vs {lim[1]} V ({lim[2]})")
print(f"assumptions: meter 5V = {VM} V, V5 = {V5:.2f} V")
print("coverage gaps:", sorted(set(missing)) or "none")
print("\n".join(bad) or "no pin above its limit")

# ---- back-feeding: CoreInk switched off (its 3V3 rail at 0 V) while the meter powers the P1-BASE ----------
# An ESP32 pin then conducts through its ESD diode into the dead 3V3 rail (~0.5 V drop). Thevenin source per pin:
print("\nCoreInk off, meter on: current into each ESP32 input (pin clamp ~0.5 V to a 0 V rail)")
BACKFEED = {  # net: (open-circuit voltage, source resistance, when)
    "G36_VMETER": (th(VM, 100e3, 68e3), 100e3 * 68e3 / 168e3, "whenever the meter supplies 5 V: continuous"),
    "G34_EXTREQ": (th(VM, 47e3, 68e3), 47e3 * 68e3 / 115e3, "only while the existing reader requests data"),
}
for net, (v, r, when) in BACKFEED.items():
    i = max(0.0, v - 0.5) / r
    print(f"  {net:11s} {v:.2f} V via {r / 1e3:5.1f} kohm -> {i * 1e6:6.0f} uA  ({when})")
