"""Generate the P1-BASE v3 schematic (pcb/needforheat-p1-base-hardware.kicad_sch).

Two parts:
* PARTS: every part with its symbol, value, footprint, LCSC number and the net on each pin.
  This is the source of truth for the netlist.
* draw(): the drawing. Parts are placed by hand on a 1.27 mm grid, connected with wires inside
  each block; power rails use power symbols and signals between blocks use net labels.

After writing, the script exports the netlist with kicad-cli and checks that it equals PARTS,
so the drawing can never silently differ from the intended circuit.

Drawing conventions (distilled from the NeedForHeat/Twomes hardware repositories):
A3, one sheet; one dashed frame per function block with a numbered title; signal flow left to
right; supplies up, ground down; wires inside a block, labels between blocks; every net named;
references and values horizontal; notes on the sheet for anything that is not obvious;
revision history bottom left and a complete title block.

Run with any Python 3:  python tools/gen_schematic.py
"""
import collections
import copy
import os
import subprocess
import sys
import tempfile
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import Sym as S, dump, parse, find, first  # noqa: E402
import kicadlib  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(ROOT, "pcb")
PROJECT = "needforheat-p1-base-hardware"
CUSTOM_LIB = os.path.join(PCB, "p1base.kicad_sym")
CLI = os.environ.get("KICAD_CLI", os.path.expandvars(r"%LOCALAPPDATA%\Programs\KiCad\10.0\bin\kicad-cli.exe"))
NS = uuid.UUID("6f1c2b4e-6b0e-4c55-9d7a-1f2e3d4c5b6a")
POWER_NETS = ("GND", "V5", "VMETER")  # drawn with power symbols (global nets)


def uid(*k):
    return str(uuid.uuid5(NS, "/".join(map(str, k))))


# --------------------------------------------------------------------------
# Custom symbols (written to pcb/p1base.kicad_sym); all pins on the 2.54 mm grid
# --------------------------------------------------------------------------
def _pin(typ, x, y, ang, name, num, length=2.54):
    font_ = [S("effects"), [S("font"), [S("size"), 1.27, 1.27]]]
    return [S("pin"), S(typ), S("line"), [S("at"), x, y, ang], [S("length"), length],
            [S("name"), name, font_], [S("number"), num, font_]]


def _prop(k, v, x, y, hide=False):
    eff = [S("effects"), [S("font"), [S("size"), 1.27, 1.27]]]
    if hide:
        eff.append([S("hide"), S("yes")])
    return [S("property"), k, v, [S("at"), x, y, 0], eff]


def _box_symbol(name, ref, value, fp, desc, left, right, bottom=(), half_w=5.08, hide_numbers=False):
    """left/right: (num, name, type) from top to bottom, 2.54 mm apart; bottom: left to right."""
    n = max(len(left), len(right))
    top_y = 2.54 * ((n - 1) // 2)
    ys = [round(top_y - 2.54 * i, 2) for i in range(n)]
    y0, y1 = top_y + 2.54, ys[-1] - (5.08 if bottom else 2.54)
    pins = [_pin(t, -half_w - 2.54, ys[i], 0, nm, num) for i, (num, nm, t) in enumerate(left)]
    pins += [_pin(t, half_w + 2.54, ys[i], 180, nm, num) for i, (num, nm, t) in enumerate(right)]
    pins += [_pin(t, round(2.54 * (i - len(bottom) // 2), 2), y1 - 2.54, 90, nm, num)
             for i, (num, nm, t) in enumerate(bottom)]
    body = [S("symbol"), name + "_0_1",
            [S("rectangle"), [S("start"), -half_w, y0], [S("end"), half_w, y1],
             [S("stroke"), [S("width"), 0.254], [S("type"), S("default")]], [S("fill"), [S("type"), S("background")]]]]
    extra = [[S("pin_numbers"), [S("hide"), S("yes")]]] if hide_numbers else []
    return [S("symbol"), name, [S("pin_names"), [S("offset"), 1.016]]] + extra + [
            [S("exclude_from_sim"), S("no")], [S("in_bom"), S("yes")], [S("on_board"), S("yes")],
            _prop("Reference", ref, 0, y0 + 1.27), _prop("Value", value, 0, y1 - 1.27),
            _prop("Footprint", fp, 0, y1 - 3.81, True), _prop("Datasheet", "", 0, 0, True),
            _prop("Description", desc, 0, 0, True),
            body, [S("symbol"), name + "_1_1"] + pins]


def _rename(e, old, new):
    if isinstance(e, list):
        return [_rename(x, old, new) for x in e]
    if isinstance(e, str) and not isinstance(e, S):
        return e.replace(old, new)
    return e


def _power_symbol(net):
    """A supply symbol (arrow up) for `net`, derived from KiCad's power:+5V."""
    s = copy.deepcopy(kicadlib.load_symbol("power:+5V"))
    s[1] = "+5V"
    s = _rename(s, "+5V", net)
    return s


def write_custom_lib():
    tp = _box_symbol(
        "TP4056", "U", "TP4056", "Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm",
        "1 A linear Li-ion charger, charge current set by PROG (I = 1200 V / R_PROG)",
        left=[("4", "VCC", "power_in"), ("8", "CE", "input"), ("2", "PROG", "passive"), ("1", "TEMP", "input")],
        right=[("5", "BAT", "power_out"), ("7", "~{CHRG}", "open_collector"), ("6", "~{STDBY}", "open_collector")],
        bottom=[("3", "GND", "power_in"), ("9", "EP", "passive")], half_w=7.62)
    bus = _box_symbol(
        "CoreInk_Bus", "J", "CoreInk bus", "p1base:CoreInk_Bus_2x08_P2.54mm",
        "M5Stack CoreInk 2x8 back connector (CoreInk-Bus); pads named after the CoreInk signals",
        left=[("GND", "GND", "passive"), ("5VIN", "5V_IN", "passive"), ("RST", "EXT_RST", "passive"),
              ("G13", "G13", "passive"), ("G21", "G21/SDA", "passive"), ("G18", "G18/SCK", "passive"),
              ("G34", "G34", "passive"), ("G23", "G23/MOSI", "passive")],
        right=[("BAT", "BAT", "passive"), ("5VOUT", "5V_OUT", "passive"), ("3V3", "3V3", "passive"),
               ("G14", "G14", "passive"), ("G22", "G22/SCL", "passive"), ("G36", "G36", "passive"),
               ("G26", "G26", "passive"), ("G25", "G25", "passive")], half_w=10.16, hide_numbers=True)
    lib = [S("kicad_symbol_lib"), [S("version"), 20231120], [S("generator"), "gen_schematic.py"],
           [S("generator_version"), "1.0"], tp, bus, _power_symbol("V5"), _power_symbol("VMETER")]
    with open(CUSTOM_LIB, "w", encoding="utf8", newline="\n") as f:
        f.write(dump(lib) + "\n")


# --------------------------------------------------------------------------
# The circuit (source of truth for the netlist)
# --------------------------------------------------------------------------
R0603 = "Resistor_SMD:R_0603_1608Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SOT235 = "Package_TO_SOT_SMD:SOT-23-5"
LED0603 = "LED_SMD:LED_0603_1608Metric"
RJ = "p1base:RJ12_EVERCOM_5301-6P6C"  # 11.45 mm high
TP_FP = "TestPoint:TestPoint_Pad_D1.0mm"

RES_LCSC = {"0R": "C21189", "47R": "C23182", "100R": "C22775", "220R": "C22962", "1k": "C21190", "2k2": "C4190", "4k7": "C23162",
            "3k3": "C22978", "10k": "C25804", "20k": "C4184", "47k": "C25819", "68k": "C23231", "100k": "C25803"}


def R(ref, val, n1, n2, dnp=False):
    return dict(ref=ref, lib="Device:R", value=val, fp=R0603, lcsc=RES_LCSC[val], nets={"1": n1, "2": n2}, dnp=dnp)


def C(ref, val, n1, n2):
    lc = {"22n": ("C21122", C0603), "100n": ("C14663", C0603), "1u": ("C15849", C0603), "10u": ("C15850", C0805)}[val]
    return dict(ref=ref, lib="Device:C", value=val, fp=lc[1], lcsc=lc[0], nets={"1": n1, "2": n2})


def NMOS(ref, g, d, s):
    return dict(ref=ref, lib="Transistor_FET:2N7002", value="2N7002", fp=SOT23, lcsc="C8545", nets={"1": g, "2": s, "3": d})


def PMOS(ref, g, d, s):
    return dict(ref=ref, lib="Transistor_FET:AO3401A", value="AO3401A", fp=SOT23, lcsc="C15127", nets={"1": g, "2": s, "3": d})


def ESD(ref, line):
    return dict(ref=ref, lib="Device:D_TVS", value="PESD5V0S1BB", fp="Diode_SMD:D_SOD-523", lcsc="C2687128",
                nets={"1": line, "2": "GND"})


def LED(ref, color, a, k):
    lc = {"green": "C12624", "yellow": "C2287", "red": "C2286"}[color]
    return dict(ref=ref, lib="Device:LED", value=f"LED {color}", fp=LED0603, lcsc=lc, nets={"2": a, "1": k})


def TP(ref, net):
    return dict(ref=ref, lib="Connector:TestPoint", value=net, fp=TP_FP, lcsc="", nets={"1": net}, bom=False)


PARTS = [
    # 1. meter connector, protection, supplies
    dict(ref="J2", lib="Connector:6P6C", value="RJ12 to meter", fp=RJ, lcsc="C3097716",
         nets={"1": "P1_5V", "2": "METER_REQ_RAW", "3": "GND", "4": None, "5": "P1_DATA_RAW", "6": "GND"}),
    PMOS("Q1", "Q1_G", "P1_5V", "VMETER"),
    R("R1", "10k", "Q1_G", "GND"),
    dict(ref="D1", lib="Device:D_Zener", value="SMF6.0A", fp="Diode_SMD:D_SMF", lcsc="C178260",
         nets={"1": "VMETER", "2": "GND"}),
    C("C1", "1u", "VMETER", "GND"),
    C("C2", "100n", "VMETER", "GND"),
    R("R21", "100k", "VMETER", "G36_VMETER"),
    R("R22", "68k", "G36_VMETER", "GND"),
    C("C6", "100n", "G36_VMETER", "GND"),
    dict(ref="D2", lib="Diode:BAT54C", value="BAT54C", fp=SOT23, lcsc="C37704",
         nets={"1": "VMETER", "2": "COREINK_5VOUT", "3": "V5"}),
    C("C3", "1u", "V5", "GND"),
    # 2. data in, Schmitt trigger, active splitter
    ESD("D3", "P1_DATA_RAW"),
    R("R2", "100R", "P1_DATA_RAW", "P1_DATA"),
    R("R3", "1k", "P1_DATA", "V5"),
    dict(ref="U1", lib="74xGxx:74LVC1G14", value="74LVC1G14", fp=SOT235, lcsc="C7835",
         nets={"1": None, "2": "P1_DATA", "3": "GND", "4": "SPLIT_DRV", "5": "V5"}),
    C("C4", "100n", "V5", "GND"),
    R("R7", "2k2", "V5", "LED1_A"),
    LED("LED1", "green", "LED1_A", "SPLIT_DRV"),
    # second Schmitt trigger at the CoreInk's 3.3 V: drives G13, and nothing flows into a switched-off CoreInk
    dict(ref="U4", lib="74xGxx:74LVC1G14", value="74LVC1G14", fp=SOT235, lcsc="C7835",
         nets={"1": None, "2": "P1_DATA", "3": "GND", "4": "G13_RX", "5": "COREINK_3V3"}),
    C("C10", "100n", "COREINK_3V3", "GND"),
    NMOS("Q2", "SPLIT_DRV", "EXT_DATA_FET", "GND"),
    R("R5", "47R", "EXT_DATA_FET", "EXT_DATA_OUT"),
    R("R6", "10k", "EXT_DATA_OUT", "V5", dnp=True),
    ESD("D4", "EXT_DATA_OUT"),
    # 3. existing reader
    dict(ref="J3", lib="Connector:6P6C", value="RJ12 existing reader", fp=RJ, lcsc="C3097716",
         nets={"1": "VMETER", "2": "EXT_REQ_RAW", "3": "GND", "4": None, "5": "EXT_DATA_OUT", "6": "GND"}),
    # 4. data request
    ESD("D5", "METER_REQ_RAW"),
    R("R8", "100R", "METER_REQ_RAW", "METER_REQ"),
    R("R9", "100k", "METER_REQ", "GND"),
    PMOS("Q3", "REQ_GATE", "METER_REQ", "V5"),
    R("R10", "100k", "REQ_GATE", "V5"),
    R("R15", "0R", "REQ_GATE", "GND", dnp=True),
    R("R20", "3k3", "V5", "LED2_A"),
    LED("LED2", "yellow", "LED2_A", "REQ_GATE"),
    NMOS("Q4", "REQ_EN", "REQ_GATE", "GND"),
    R("R11", "1k", "G26_REQ", "REQ_EN"),
    R("R12", "100k", "REQ_EN", "GND"),
    NMOS("Q5", "EXT_REQ_G", "REQ_GATE", "GND"),
    R("R13", "10k", "EXT_REQ", "EXT_REQ_G"),
    R("R14", "100k", "EXT_REQ_G", "GND"),
    ESD("D6", "EXT_REQ_RAW"),
    R("R16", "100R", "EXT_REQ_RAW", "EXT_REQ"),
    dict(ref="D7", lib="Diode:1N5819WS", value="1N5819WS", fp="Diode_SMD:D_SOD-323", lcsc="C191023",
         nets={"2": "EXT_REQ", "1": "METER_REQ"}),
    R("R18", "47k", "EXT_REQ", "G34_EXTREQ"),
    R("R19", "68k", "G34_EXTREQ", "GND"),
    # 5. charger
    PMOS("Q6", "CHG_GATE", "CHG_IN", "VMETER"),
    R("R23", "100k", "CHG_GATE", "VMETER"),
    C("C7", "22n", "CHG_GATE", "CHG_IN"),
    R("R24", "47k", "CHG_GATE", "CHG_GATE_DRV"),
    NMOS("Q7", "CHG_EN", "CHG_GATE_DRV", "GND"),
    R("R25", "1k", "G25_CHG", "CHG_EN"),
    R("R26", "100k", "CHG_EN", "GND"),
    C("C8", "10u", "CHG_IN", "GND"),
    R("R31", "2k2", "CHG_IN", "LED3_A"),
    LED("LED3", "red", "LED3_A", "CHRG_N"),
    dict(ref="U3", lib="p1base:TP4056", value="TP4056", fp="Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm",
         lcsc="C16581", nets={"4": "CHG_IN", "8": "CHG_IN", "2": "PROG", "1": "GND", "5": "COREINK_BAT",
                              "7": "CHRG_N", "6": None, "3": "GND", "9": "GND"}),
    R("R27", "20k", "PROG", "GND"),
    R("R28", "20k", "PROG", "PROG_HI"),
    NMOS("Q8", "CHG_HI", "PROG_HI", "GND"),
    R("R29", "1k", "G14_CHGHI", "CHG_HI"),
    R("R30", "100k", "CHG_HI", "GND"),
    C("C9", "10u", "COREINK_BAT", "GND"),
    # 6. CoreInk bus
    dict(ref="J1", lib="p1base:CoreInk_Bus", value="CoreInk bus", fp="p1base:CoreInk_Bus_2x08_P2.54mm", lcsc="C21241050",
         nets={"GND": "GND", "BAT": "COREINK_BAT", "5VIN": None, "5VOUT": "COREINK_5VOUT", "RST": None,
               "3V3": "COREINK_3V3", "G13": "G13_RX", "G14": "G14_CHGHI", "G21": None, "G22": None, "G18": None,
               "G36": "G36_VMETER", "G34": "G34_EXTREQ", "G26": "G26_REQ", "G23": None, "G25": "G25_CHG"}),
    # 7. test points, peg holes
    TP("TP1", "VMETER"), TP("TP2", "V5"), TP("TP3", "P1_DATA"), TP("TP4", "METER_REQ"),
    TP("TP5", "EXT_DATA_OUT"), TP("TP6", "CHG_IN"), TP("TP7", "GND"),
] + [dict(ref=f"H{i}", lib="Mechanical:MountingHole", value="Peg hole 2.2 mm", fp="MountingHole:MountingHole_2.2mm_M2",
          lcsc="", nets={}, bom=False) for i in (1, 2, 3)]


# --------------------------------------------------------------------------
# Drawing primitives
# --------------------------------------------------------------------------
def rot_pt(x, y, rot):
    return {0: (x, y), 90: (-y, x), 180: (-x, -y), 270: (y, -x)}[rot]


def font(size=1.27, justify=None, hide=False, bold=False):
    f = [S("font"), [S("size"), size, size]]
    if bold:
        f.append([S("bold"), S("yes")])
    e = [S("effects"), f]
    if justify and justify != "center":
        e.append([S("justify")] + [S(x) for x in justify.split()])
    if hide:
        e.append([S("hide"), S("yes")])
    return e


def r2(v):
    return round(v + 0.0, 2)


class Sheet:
    def __init__(self):
        self.parts = {p["ref"]: p for p in PARTS}
        self.lib = {}
        self.items = []
        self.placed = {}
        self.wires = []      # (a, b)
        self.anchors = []    # connection points of power symbols and flags (for junctions)
        self.labels = []     # (name, point): checked to sit on a wire end or a pin
        self.npwr = 0
        self.dx = self.dy = 0.0

    # ---- coordinates -----------------------------------------------------
    def at(self, x, y):
        return (r2(x + self.dx), r2(y + self.dy))

    def block(self, title, x0, y0, x1, y1, dx=0.0, dy=0.0):
        """Dashed frame with a title; following coordinates are shifted by (dx, dy)."""
        self.dx, self.dy = dx, dy
        self.items.append([S("rectangle"), [S("start"), x0, y0], [S("end"), x1, y1],
                           [S("stroke"), [S("width"), 0.2], [S("type"), S("dash")], [S("color"), 0, 0, 132, 1]],
                           [S("fill"), [S("type"), S("none")]], [S("uuid"), uid("frame", title)]])
        self.items.append([S("text"), title, [S("exclude_from_sim"), S("no")], [S("at"), x0 + 2.54, y0 + 5.08, 0],
                           font(2.54, "left bottom", bold=True), [S("uuid"), uid("blk", title)]])

    def note(self, text, x, y, size=1.27):
        x, y = self.at(x, y)
        self.items.append([S("text"), text, [S("exclude_from_sim"), S("no")], [S("at"), x, y, 0],
                           font(size, "left bottom"), [S("uuid"), uid("note", text[:40], x, y)]])

    def _sym(self, lid):
        if lid not in self.lib:
            self.lib[lid] = kicadlib.load_symbol(lid, {"p1base": CUSTOM_LIB})
        return self.lib[lid]

    # ---- parts -----------------------------------------------------------
    def place(self, ref, x, y, rot=0, mirror=None, side=None):
        p = self.parts[ref]
        lid = p["lib"]
        sym = self._sym(lid)
        X, Y = self.at(x, y)
        pins = {}
        for pin in kicadlib.pins(sym):
            if pin["unit"] not in (0, 1):
                continue
            px, py = pin["x"], pin["y"]
            if mirror == "x":
                py = -py
            elif mirror == "y":
                px = -px
            dx, dy = rot_pt(px, py, rot)
            pins[pin["number"]] = (r2(X + dx), r2(Y - dy))
        self.placed[ref] = dict(X=X, Y=Y, rot=rot, mirror=mirror, pins=pins)
        for num, net in p["nets"].items():
            if net is None:
                x_, y_ = pins[num]
                self.items.append([S("no_connect"), [S("at"), x_, y_], [S("uuid"), uid(ref, "nc", num)]])
        fields = self._fields(p, X, Y, rot, mirror, side)
        props = []
        for k, v, (fx, fy), ang, just, hide in fields:
            props.append([S("property"), k, v, [S("at"), r2(fx), r2(fy), ang], font(justify=just, hide=hide)])
        dnp = bool(p.get("dnp"))
        in_bom = p.get("bom", True) and not dnp
        s = [S("symbol"), [S("lib_id"), lid], [S("at"), X, Y, rot]]
        if mirror:
            s.append([S("mirror"), S(mirror)])
        s += [[S("unit"), 1], [S("exclude_from_sim"), S("no")], [S("in_bom"), S("yes" if in_bom else "no")],
              [S("on_board"), S("yes")], [S("dnp"), S("yes" if dnp else "no")], [S("uuid"), uid(ref, "sym")]] + props
        s += [[S("pin"), n, [S("uuid"), uid(ref, "pin", n)]] for n in pins]
        s.append([S("instances"), [S("project"), PROJECT, [S("path"), "/" + uid("sheet"), [S("reference"), ref],
                                                             [S("unit"), 1]]]])
        self.items.append(s)

    def _fields(self, p, X, Y, rot, mirror, side):
        """Reference and value placement, always horizontal and clear of the pins."""
        lid, ref, val = p["lib"], p["ref"], p["value"]
        hid = [("Footprint", p["fp"], (X, Y), 0, None, True), ("Datasheet", "", (X, Y), 0, None, True)]
        if p.get("lcsc"):
            hid.append(("LCSC", p["lcsc"], (X, Y), 0, None, True))
        ang = 90 if rot in (90, 270) else 0
        # KiCad keeps text readable, which mirrors the justification for rotation 90/180 and for mirror y
        flip = (rot in (90, 180)) != (mirror == "y")
        L, Rj = ("right", "left") if flip else ("left", "right")
        two = lid in ("Device:R", "Device:C")
        diode = lid in ("Device:LED", "Device:D_TVS", "Device:D_Zener", "Diode:1N5819WS")
        hide_val = lid == "Connector:TestPoint"
        right = [((X + 2.54, Y - 0.635), L), ((X + 2.54, Y + 1.905), L)]
        left = [((X - 2.54, Y - 0.635), Rj), ((X - 2.54, Y + 1.905), Rj)]
        if (two and rot in (0, 180)) or (diode and rot in (90, 270)):
            f = left if side == "left" else right
        elif two:
            f = [((X, Y - 3.81), "center"), ((X, Y - 1.905), "center")] if side == "above" else \
                [((X, Y - 1.905), "center"), ((X, Y + 3.175), "center")]
        elif diode:
            f = [((X, Y - 2.54), "center"), ((X, Y + 3.81), "center")]
        elif lid.startswith("Transistor_FET"):
            if rot == 90:      # gate down
                f = [((X + 1.27, Y + 3.81), L), ((X + 1.27, Y + 6.35), L)]
            elif rot == 270:   # gate up
                f = [((X, Y + 6.35), "center"), ((X, Y + 8.89), "center")]
            elif side == "top_r":
                f = [((X + 3.81, Y - 6.35), L), ((X + 3.81, Y - 4.445), L)]
            elif side == "top" and mirror == "y":
                f = [((X - 3.81, Y - 6.35), Rj), ((X - 3.81, Y - 4.445), Rj)]
            elif side == "top":
                f = [((X + 3.81, Y - 6.35), L), ((X + 3.81, Y - 4.445), L)]
            elif (side == "left") != (mirror == "y"):
                f = [((X - 5.08, Y - 0.635), Rj), ((X - 5.08, Y + 1.905), Rj)]
            else:
                f = [((X + 5.08, Y - 0.635), L), ((X + 5.08, Y + 1.905), L)]
        elif lid == "Diode:BAT54C":
            f = [((X, Y - 6.35), "center"), ((X, Y - 4.445), "center")]
        elif lid == "74xGxx:74LVC1G14":
            f = [((X + 2.54, Y + 5.715), "left"), ((X + 2.54, Y + 7.62), "left")]
        elif lid == "p1base:TP4056":
            f = [((X, Y - 8.89), "center"), ((X, Y - 6.35), "center")]
        elif lid == "p1base:CoreInk_Bus":
            f = [((X, Y - 13.97), "center"), ((X, Y + 15.24), "center")]
        elif lid == "Connector:6P6C":
            f = [((X - 2.54, Y - 15.24), "center"), ((X - 2.54, Y - 13.335), "center")]
        elif lid == "Connector:TestPoint":
            f = [((X, Y - 5.715), "center"), ((X, Y - 7.62), "center")]
        elif lid == "Mechanical:MountingHole":
            f = [((X + 3.81, Y - 0.635), "left"), ((X + 3.81, Y + 1.905), "left")]
        else:
            f = right
        ang_ = ang if (two or diode or lid.startswith("Transistor_FET")) else 0
        return [("Reference", ref, f[0][0], ang_, f[0][1], False),
                ("Value", val, f[1][0], ang_, f[1][1], hide_val)] + hid

    def pin(self, spec):
        """'R1.2' -> absolute pin position; tuples are shifted by the current block offset."""
        if isinstance(spec, str):
            ref, num = spec.split(".", 1)
            return self.placed[ref]["pins"][num]
        return self.at(*spec)

    # ---- connections -----------------------------------------------------
    def wire(self, *pts, first="h"):
        """Wire through the points; an L-corner is added between points that are not aligned."""
        P = [self.pin(p) for p in pts]
        seq = [P[0]]
        for b in P[1:]:
            a = seq[-1]
            if a[0] != b[0] and a[1] != b[1]:
                seq.append((b[0], a[1]) if first == "h" else (a[0], b[1]))
            seq.append(b)
        for a, b in zip(seq, seq[1:]):
            if a != b:
                self.wires.append((a, b))
                self.items.append([S("wire"), [S("pts"), [S("xy"), *a], [S("xy"), *b]],
                                   [S("stroke"), [S("width"), 0], [S("type"), S("default")]],
                                   [S("uuid"), uid("w", a, b)]])
        return seq[-1]

    def label(self, name, pt, d="r", size=1.27):
        x, y = self.pin(pt)
        ang, just = {"r": (0, "left bottom"), "l": (180, "right bottom"), "u": (90, "left bottom"),
                     "d": (270, "right bottom")}[d]
        self.labels.append((name, (x, y)))
        self.items.append([S("label"), name, [S("at"), x, y, ang], font(size, just), [S("uuid"), uid("lbl", name, x, y)]])

    def stub(self, pin, name, length=5.08, d="r"):
        """Short wire from a pin, ending in a net label."""
        x, y = self.pin(pin)
        dx, dy = {"r": (length, 0), "l": (-length, 0), "u": (0, -length), "d": (0, length)}[d]
        end = (r2(x + dx), r2(y + dy))
        self.wire((x - self.dx, y - self.dy), (end[0] - self.dx, end[1] - self.dy))
        self.label(name, (end[0] - self.dx, end[1] - self.dy), d)

    def power(self, net, pt):
        x, y = self.pin(pt)
        self.npwr += 1
        ref = f"#PWR{self.npwr:03d}"
        if net == "GND":
            lid, vpos, rot = "power:GND", (x, y + 4.445), 0
        elif net == "PWR_FLAG":
            lid, vpos, rot = "power:PWR_FLAG", (x, y - 4.445), 0
            ref = f"#FLG{self.npwr:03d}"
        else:
            lid, vpos, rot = "p1base:" + net, (x, y - 4.445), 0
        self._sym(lid)
        self.anchors.append((x, y))
        sym = self.lib[lid]
        pins = [p["number"] for p in kicadlib.pins(sym)]
        self.items.append([S("symbol"), [S("lib_id"), lid], [S("at"), x, y, rot], [S("unit"), 1],
                           [S("exclude_from_sim"), S("no")], [S("in_bom"), S("no")], [S("on_board"), S("yes")],
                           [S("dnp"), S("no")], [S("uuid"), uid(ref, "sym")],
                           [S("property"), "Reference", ref, [S("at"), x, y, 0], font(hide=True)],
                           [S("property"), "Value", "PWR_FLAG" if net == "PWR_FLAG" else net,
                            [S("at"), vpos[0], vpos[1], 0], font(justify="center", hide=net == "GND")],
                           [S("property"), "Footprint", "", [S("at"), x, y, 0], font(hide=True)],
                           [S("property"), "Datasheet", "", [S("at"), x, y, 0], font(hide=True)]]
                          + [[S("pin"), n, [S("uuid"), uid(ref, "pin", n)]] for n in pins]
                          + [[S("instances"), [S("project"), PROJECT, [S("path"), "/" + uid("sheet"),
                                                                         [S("reference"), ref], [S("unit"), 1]]]]])

    def check_labels(self):
        ends = {pt for w in self.wires for pt in w}
        pinpts = {pt for pl in self.placed.values() for pt in pl["pins"].values()}
        bad = [f"{n} at {pt}" for n, pt in self.labels if pt not in ends and pt not in pinpts]
        if bad:
            raise SystemExit("labels not on a wire end or pin: " + ", ".join(bad))

    def junctions(self):
        pinpts = collections.Counter(pt for pl in self.placed.values() for pt in pl["pins"].values())
        ends = collections.Counter(pt for w in self.wires for pt in w)
        pts = set(ends)
        for pt in pts:
            n = ends[pt] + pinpts[pt] + self.anchors.count(pt)
            for a, b in self.wires:
                if pt not in (a, b) and (min(a[0], b[0]) <= pt[0] <= max(a[0], b[0])) and \
                        (min(a[1], b[1]) <= pt[1] <= max(a[1], b[1])):
                    n += 2
            if n >= 3:
                self.items.append([S("junction"), [S("at"), *pt], [S("diameter"), 0], [S("color"), 0, 0, 0, 0],
                                   [S("uuid"), uid("j", pt)]])


# --------------------------------------------------------------------------
# The drawing (A3, mm, y down)
# --------------------------------------------------------------------------
def draw(s):
    # 1 ---------------------------------------------------------------------
    s.block("1  Meter connector, reverse-polarity protection, supplies", 15.24, 15.24, 152.4, 119.38)
    s.place("J2", 30.48, 50.8, mirror="x")
    s.place("Q1", 73.66, 38.1, rot=90)
    s.place("R1", 73.66, 50.8)
    s.place("D1", 83.82, 43.18, rot=270)
    s.place("C1", 96.52, 43.18)
    s.place("C2", 106.68, 43.18)
    s.place("R21", 116.84, 43.18)
    s.place("R22", 116.84, 54.61)
    s.place("C6", 127.0, 54.61)
    s.wire("J2.1", (45.72, 45.72), (45.72, 35.56), (55.88, 35.56), "Q1.3", first="v")
    s.label("P1_5V", (55.88, 35.56))
    s.wire("Q1.1", (73.66, 45.72), "R1.1")
    s.label("Q1_G", (73.66, 45.72), "l", 1.0)
    s.power("GND", "R1.2")
    s.wire("Q1.2", (83.82, 35.56), (96.52, 35.56), (106.68, 35.56), (116.84, 35.56), (134.62, 35.56))
    s.power("VMETER", (134.62, 35.56))
    for r in ("D1.1", "C1.1", "C2.1", "R21.1"):
        x, y = s.pin(r)
        s.wire((x, 35.56), r)
    for r in ("D1.2", "C1.2", "C2.2", "R22.2", "C6.2"):
        s.power("GND", r)
    s.wire("R21.2", (116.84, 48.26), "R22.1")
    s.wire((116.84, 48.26), (127.0, 48.26), (134.62, 48.26))
    s.wire((127.0, 48.26), "C6.1")
    s.label("G36_VMETER", (134.62, 48.26))
    s.wire("J2.3", (43.18, 50.8), (43.18, 58.42), (43.18, 60.96))
    s.wire("J2.6", (43.18, 58.42))
    s.power("GND", (43.18, 60.96))
    s.stub("J2.2", "METER_REQ_RAW", 7.62)
    s.stub("J2.5", "P1_DATA_RAW", 7.62)
    s.note("To the smart meter (P1 port).", 20.32, 71.12)
    s.note("Q1: reverse-polarity protection (conducts only", 83.82, 68.58)
    s.note("with the meter's 5 V on pin 1). D1: surge clamp.", 83.82, 71.12)
    s.note("G36 reads the meter voltage (x 0.405).", 83.82, 73.66)
    s.place("D2", 60.96, 88.9)
    s.place("C3", 71.12, 102.87)
    s.wire("D2.1", (48.26, 88.9))
    s.power("VMETER", (48.26, 88.9))
    s.stub("D2.2", "COREINK_5VOUT", 7.62)
    s.wire("D2.3", (60.96, 99.06), (71.12, 99.06), (81.28, 99.06))
    s.wire((71.12, 99.06), "C3.1")
    s.power("GND", "C3.2")
    s.power("V5", (81.28, 99.06))
    s.note("V5 = meter 5 V or CoreInk 5V_OUT, whichever is higher;", 83.82, 104.14)
    s.note("powers the input, the splitter and the data request.", 83.82, 106.68)

    # 2 ---------------------------------------------------------------------
    s.block("2  P1 data input, Schmitt trigger, active splitter", 157.48, 15.24, 320.04, 119.38, dx=12.7)
    s.place("D3", 170.18, 60.96, rot=270)
    s.place("R2", 180.34, 55.88, rot=90)
    s.place("R3", 190.5, 46.99, rot=180)
    s.place("U1", 210.82, 55.88)
    s.place("C4", 215.9, 44.45)
    s.place("R7", 228.6, 35.56)
    s.place("LED1", 228.6, 46.99, rot=90)
    s.place("Q2", 243.84, 55.88)
    s.place("R5", 261.62, 45.72, rot=90)
    s.place("R6", 271.78, 38.1, rot=180)
    s.place("D4", 279.4, 50.8, rot=270)
    s.place("U4", 210.82, 88.9)
    s.place("C10", 215.9, 80.01)
    s.wire((162.56, 55.88), (170.18, 55.88), "R2.1")
    s.label("P1_DATA_RAW", (162.56, 55.88), "l")
    s.wire((170.18, 55.88), "D3.1")
    s.power("GND", "D3.2")
    s.wire("R2.2", (190.5, 55.88), (193.04, 55.88), "U1.2")
    s.wire((193.04, 55.88), "U4.2", first="v")
    s.label("P1_DATA", (190.5, 55.88), "r", 1.0)
    s.wire("R3.1", (190.5, 55.88))
    s.power("V5", "R3.2")
    s.wire("U1.5", (205.74, 40.64), (205.74, 38.1))
    s.wire((205.74, 40.64), (215.9, 40.64), "C4.1")
    s.power("V5", (205.74, 38.1))
    s.power("GND", "C4.2")
    s.power("GND", "U1.3")
    s.wire("U1.4", (228.6, 55.88), (231.14, 55.88), "Q2.1")
    s.wire((231.14, 55.88), (231.14, 60.96))
    s.label("SPLIT_DRV", (231.14, 60.96), "r", 1.0)
    s.wire("LED1.1", (228.6, 55.88))
    s.wire("LED1.2", (228.6, 41.91), "R7.2")
    s.label("LED1_A", (228.6, 41.91), "r", 1.0)
    s.power("V5", "R7.1")
    s.power("GND", "Q2.2")
    s.wire("Q2.3", (246.38, 45.72), "R5.1", first="v")
    s.label("EXT_DATA_FET", (246.38, 45.72), "r", 1.0)
    s.wire("R5.2", (271.78, 45.72), (279.4, 45.72), (289.56, 45.72))
    s.wire("R6.1", (271.78, 45.72))
    s.power("V5", "R6.2")
    s.wire((279.4, 45.72), "D4.1")
    s.power("GND", "D4.2")
    s.label("EXT_DATA_OUT", (289.56, 45.72))
    s.wire("U4.5", (205.74, 76.2), (215.9, 76.2), (223.52, 76.2))
    s.wire((215.9, 76.2), "C10.1")
    s.power("GND", "C10.2")
    s.label("COREINK_3V3", (223.52, 76.2))
    s.power("GND", "U4.3")
    s.wire("U4.4", (236.22, 88.9))
    s.label("G13_RX", (236.22, 88.9))
    s.note("U1: Schmitt trigger at V5 with the 1 k pull-up of v2.7 (reads weak meter outputs).", 160.02, 106.68)
    s.note("Q2 drives the existing reader from V5, so it keeps working when the CoreInk is off. R6 (not fitted):", 160.02, 109.22)
    s.note("pull-up for readers without their own. LED1 (green): blinks with the meter data.", 160.02, 111.76)
    s.note("U4: same Schmitt trigger at the CoreInk's 3.3 V; G13 = P1 RX (not inverted). Unpowered when the", 160.02, 114.3)
    s.note("CoreInk is off, so no current flows into the ESP32 (power-off isolation).", 160.02, 116.84)

    # 3 ---------------------------------------------------------------------
    s.block("3  Existing P1 reader", 325.12, 15.24, 405.13, 119.38)
    s.place("J3", 388.62, 55.88, rot=180)
    s.wire("J3.1", (370.84, 50.8))
    s.power("VMETER", (370.84, 50.8))
    s.stub("J3.2", "EXT_REQ_RAW", 17.78, "l")
    s.wire("J3.3", (373.38, 55.88), (373.38, 63.5), (373.38, 66.04))
    s.wire("J3.6", (373.38, 63.5))
    s.power("GND", (373.38, 66.04))
    s.stub("J3.5", "EXT_DATA_OUT", 17.78, "l")
    s.note("For a reader that was already on the meter", 330.2, 86.36)
    s.note("(HomeWizard P1 meter, ...): it gets the meter's", 330.2, 88.9)
    s.note("5 V and a buffered copy of the data, and its", 330.2, 91.44)
    s.note("data request is passed on to the meter.", 330.2, 93.98)

    # 4 ---------------------------------------------------------------------
    s.block("4  Data request: CoreInk (G26) OR existing reader", 15.24, 124.46, 190.5, 241.3, dx=7.62)
    s.place("D5", 30.48, 182.88, rot=270)
    s.place("R8", 39.37, 177.8, rot=90)
    s.place("R9", 48.26, 184.15)
    s.place("Q3", 63.5, 167.64, rot=180, side="left")
    s.place("R10", 73.66, 160.02, rot=180)
    s.place("R15", 81.28, 173.99, side="left")
    s.place("R20", 99.06, 149.86)
    s.place("LED2", 99.06, 160.02, rot=90)
    s.place("Q4", 88.9, 185.42, side="top")
    s.place("R11", 73.66, 185.42, rot=90)
    s.place("R12", 78.74, 191.77)
    s.place("Q5", 111.76, 185.42, mirror="y", side="top_r")
    s.place("R14", 121.92, 191.77)
    s.place("R13", 129.54, 185.42, rot=270, side="above")
    s.place("D7", 142.24, 177.8, rot=270)
    s.place("R18", 137.16, 191.77)
    s.place("R19", 137.16, 203.2)
    s.place("R16", 154.94, 185.42, rot=270)
    s.place("D6", 162.56, 190.5, rot=270)
    s.wire((22.86, 177.8), (30.48, 177.8), "R8.1")
    s.label("METER_REQ_RAW", (22.86, 177.8), "l")
    s.wire((30.48, 177.8), "D5.1")
    s.power("GND", "D5.2")
    s.wire("R8.2", (48.26, 177.8), (60.96, 177.8), "Q3.3")
    s.label("METER_REQ", (48.26, 177.8), "r", 1.0)
    s.wire((48.26, 177.8), "R9.1")
    s.power("GND", "R9.2")
    s.power("V5", "Q3.2")
    s.wire("Q3.1", (73.66, 167.64), (81.28, 167.64), (91.44, 167.64), (99.06, 167.64), (109.22, 167.64))
    s.label("REQ_GATE", (81.28, 167.64), "r", 1.0)
    s.wire("R10.1", (73.66, 167.64))
    s.power("V5", "R10.2")
    s.wire((81.28, 167.64), "R15.1")
    s.power("GND", "R15.2")
    s.wire("LED2.1", (99.06, 167.64))
    s.wire("LED2.2", "R20.2")
    s.label("LED2_A", "R20.2", "l", 1.0)
    s.power("V5", "R20.1")
    s.wire("Q4.3", (91.44, 167.64))
    s.power("GND", "Q4.2")
    s.wire((66.04, 185.42), "R11.1")
    s.label("G26_REQ", (66.04, 185.42), "l")
    s.wire("R11.2", (78.74, 185.42), "Q4.1")
    s.wire((78.74, 185.42), "R12.1")
    s.label("REQ_EN", "R12.1", "r", 1.0)
    s.power("GND", "R12.2")
    s.wire("Q5.3", (109.22, 167.64))
    s.power("GND", "Q5.2")
    s.wire("Q5.1", (121.92, 185.42), "R13.2")
    s.wire((121.92, 185.42), "R14.1")
    s.label("EXT_REQ_G", "R14.1", "r", 1.0)
    s.power("GND", "R14.2")
    s.wire("R13.1", (137.16, 185.42), (142.24, 185.42), "R16.2")
    s.wire((137.16, 185.42), "R18.1")
    s.label("EXT_REQ", "R18.1", "r", 1.0)
    s.wire((142.24, 185.42), "D7.2")
    s.wire("D7.1", (142.24, 170.18), (137.16, 170.18))
    s.label("METER_REQ", (137.16, 170.18), "l")
    s.wire("R18.2", (137.16, 196.85), "R19.1")
    s.wire((137.16, 196.85), (144.78, 196.85))
    s.label("G34_EXTREQ", (144.78, 196.85))
    s.power("GND", "R19.2")
    s.wire("R16.1", (162.56, 185.42), (167.64, 185.42))
    s.wire((162.56, 185.42), "D6.1")
    s.power("GND", "D6.2")
    s.label("EXT_REQ_RAW", (167.64, 185.42))
    s.note("The meter sends when its request pin (J2 pin 2) is >= 4 V. Q3 pulls it to V5 when REQ_GATE is low:", 12.7, 218.44)
    s.note("Q4 when the CoreInk requests (G26 high), Q5 when the existing reader requests. D7 passes the reader's", 12.7, 220.98)
    s.note("own request on when V5 is absent (DSMR 2/3 meter with the CoreInk off). G34 tells the firmware that", 12.7, 223.52)
    s.note("the reader requests. R15 (not fitted): always request. LED2 (yellow): data requested.", 12.7, 226.06)

    # 5 ---------------------------------------------------------------------
    s.block("5  P1 charging of the CoreInk battery", 195.58, 124.46, 320.04, 241.3)
    s.place("Q6", 210.82, 170.18, rot=270)
    s.place("R23", 204.47, 157.48, rot=270)
    s.place("C7", 220.98, 161.29)
    s.place("R24", 229.87, 157.48, rot=90, side="above")
    s.place("Q7", 243.84, 162.56, mirror="y")
    s.place("R26", 254.0, 168.91)
    s.place("R25", 261.62, 162.56, rot=270)
    s.place("C8", 220.98, 199.39)
    s.place("R31", 236.22, 199.39)
    s.place("LED3", 236.22, 207.01, rot=90)
    s.place("U3", 276.86, 198.12)
    s.place("R27", 256.54, 207.01)
    s.place("R28", 248.92, 207.01)
    s.place("Q8", 246.38, 218.44)
    s.place("R29", 232.41, 218.44, rot=90)
    s.place("R30", 238.76, 224.79)
    s.place("C9", 297.18, 199.39)
    s.wire("R23.2", (200.66, 172.72), "Q6.2", first="v")
    s.power("VMETER", "R23.2")
    s.wire("R23.1", (210.82, 157.48), (220.98, 157.48), "R24.1")
    s.label("CHG_GATE", (210.82, 157.48), "r", 1.0)
    s.wire("Q6.1", (210.82, 157.48))
    s.wire("C7.1", (220.98, 157.48))
    s.wire("R24.2", "Q7.3")
    s.label("CHG_GATE_DRV", "R24.2", "r", 1.0)
    s.power("GND", "Q7.2")
    s.wire("Q7.1", (254.0, 162.56), "R25.2")
    s.wire((254.0, 162.56), "R26.1")
    s.label("CHG_EN", "R26.1", "r", 1.0)
    s.power("GND", "R26.2")
    s.wire("R25.1", (271.78, 162.56))
    s.label("G25_CHG", (271.78, 162.56))
    s.wire("C7.2", (220.98, 172.72), "Q6.3")
    s.wire("Q6.3", (215.9, 195.58), (220.98, 195.58), (236.22, 195.58), (264.16, 195.58), "U3.4", first="v")
    s.label("CHG_IN", (236.22, 195.58), "r", 1.0)
    s.wire((220.98, 195.58), "C8.1")
    s.power("GND", "C8.2")
    s.wire((236.22, 195.58), "R31.1")
    s.wire("R31.2", "LED3.2")
    s.label("LED3_A", "R31.2", "l", 1.0)
    s.stub("LED3.1", "CHRG_N", 5.08, "l")
    s.wire("U3.8", (264.16, 198.12), (264.16, 195.58))
    s.wire("U3.1", (264.16, 203.2), (264.16, 210.82))
    s.power("GND", (264.16, 210.82))
    s.wire("U3.2", (256.54, 200.66), (248.92, 200.66))
    s.label("PROG", (256.54, 200.66), "r", 1.0)
    s.wire((256.54, 200.66), "R27.1")
    s.power("GND", "R27.2")
    s.wire((248.92, 200.66), "R28.1")
    s.wire("R28.2", "Q8.3")
    s.label("PROG_HI", "Q8.3", "r", 1.0)
    s.power("GND", "Q8.2")
    s.wire("R29.2", (238.76, 218.44), "Q8.1")
    s.wire((238.76, 218.44), "R30.1")
    s.label("CHG_HI", "R30.1", "r", 1.0)
    s.power("GND", "R30.2")
    s.wire((223.52, 218.44), "R29.1")
    s.label("G14_CHGHI", (223.52, 218.44), "l")
    x3, y3 = s.pin("U3.3")
    s.wire("U3.3", (x3, y3 + 2.54), "U3.9", first="h")
    s.power("GND", (x3, y3 + 2.54))
    s.label("CHRG_N", "U3.7")
    s.wire("U3.5", (297.18, 195.58), (302.26, 195.58))
    s.wire((297.18, 195.58), "C9.1")
    s.power("GND", "C9.2")
    s.label("COREINK_BAT", (302.26, 195.58))
    s.note("G25 high: Q7 pulls the gate of Q6 down through R24; C7 slows the turn-on (soft start, inrush < 260 mA).", 198.12, 233.68)
    s.note("TP4056 charges the CoreInk battery: 60 mA (R27), 120 mA with G14 high (R27 || R28).", 198.12, 236.22)
    s.note("LED3 (red): charging.", 198.12, 238.76)

    # 6 ---------------------------------------------------------------------
    s.block("6  CoreInk bus (back connector)", 325.12, 124.46, 405.13, 241.3)
    s.place("J1", 365.76, 162.56)
    x, y = s.pin("J1.GND")
    s.wire("J1.GND", (x - 5.08, y))
    s.power("GND", (x - 5.08, y))
    s.stub("J1.G13", "G13_RX", 7.62, "l")
    s.stub("J1.G34", "G34_EXTREQ", 7.62, "l")
    for pin, net in (("BAT", "COREINK_BAT"), ("5VOUT", "COREINK_5VOUT"), ("3V3", "COREINK_3V3"), ("G14", "G14_CHGHI"), ("G36", "G36_VMETER"),
                     ("G26", "G26_REQ"), ("G25", "G25_CHG")):
        s.stub("J1." + pin, net, 7.62)
    for i, t in enumerate(["Firmware interface (CoreInk ESP32):",
                           "G13  P1 data in (UART RX, not inverted)",
                           "G26  request data (high = request)",
                           "G34  existing reader requests (in)",
                           "G36  meter 5 V x 0.405 (ADC)",
                           "G25  P1 charging on (high)",
                           "G14  charge current 120 mA (high) / 60 mA",
                           "BAT  CoreInk battery (charged by U3)",
                           "5V_OUT  CoreInk 5 V, feeds V5 via D2",
                           "3V3  CoreInk 3.3 V, powers U4"]):
        s.note(t, 330.2, 193.04 + 2.54 * i)

    # 7 ---------------------------------------------------------------------
    s.block("7  Test points, peg holes, ERC flags", 15.24, 246.38, 190.5, 284.48)
    for i, (tp, net) in enumerate([("TP1", "VMETER"), ("TP2", "V5"), ("TP3", "P1_DATA"), ("TP4", "METER_REQ"),
                                   ("TP5", "EXT_DATA_OUT"), ("TP6", "CHG_IN"), ("TP7", "GND")]):
        x = 22.86 + 20.32 * i
        s.place(tp, x, 260.35)
        if net == "GND":
            s.wire(f"{tp}.1", (x, 264.16))
            s.power("GND", (x, 264.16))
        elif net in POWER_NETS:
            s.wire(f"{tp}.1", (x, 264.16), (x + 5.08, 264.16), first="v")
            s.power(net, (x + 5.08, 264.16))
        else:
            s.wire(f"{tp}.1", (x, 264.16))
            s.label(net, (x, 264.16), "r", 1.0)
    for i in (1, 2, 3):
        s.place(f"H{i}", 22.86 + 22.86 * (i - 1), 276.86)
    s.note("PWR_FLAG: tells ERC that these nets are supplied", 96.52, 269.24)
    for i, net in enumerate(["GND", "VMETER", "V5", "CHG_IN", "COREINK_3V3"]):
        x = 96.52 + 17.78 * i
        s.power("PWR_FLAG", (x, 276.86))
        s.wire((x, 276.86), (x + 8.89, 276.86))
        if net in POWER_NETS:
            s.power(net, (x + 8.89, 276.86))
        else:
            s.label(net, (x + 8.89, 276.86), "r", 1.0)

    # notes, revision history -------------------------------------------------
    s.dx = s.dy = 0.0
    s.note("Revision history", 193.04, 251.46, 1.5)
    s.note("2.7  2024-06  Windesheim: optocoupler splitter, DIP switches for the data request.", 193.04, 255.27)
    s.note("3.0  2026-11  Active splitter, firmware-managed data request, P1 charging, all parts top side.", 193.04, 257.81)
    s.note("Design rationale, calculations and simulations: docs/design-v3.md.", 193.04, 262.89)
    s.note("DNP = not fitted (R6, R15).", 193.04, 265.43)


# --------------------------------------------------------------------------
# Writer and self-check
# --------------------------------------------------------------------------
def build():
    write_custom_lib()
    s = Sheet()
    draw(s)
    missing = set(s.parts) - set(s.placed)
    if missing:
        raise SystemExit(f"parts not placed: {sorted(missing)}")
    s.check_labels()
    s.junctions()
    sch = [S("kicad_sch"), [S("version"), 20231120], [S("generator"), "eeschema"], [S("generator_version"), "8.0"],
           [S("uuid"), uid("sheet")], [S("paper"), "A3"],
           [S("title_block"), [S("title"), "NeedForHeat P1-BASE"], [S("date"), "2026-11-14"], [S("rev"), "3.0"],
            [S("company"), "energiegedrag.nl"],
            [S("comment"), 1, "M5Stack CoreInk extension: P1 smart meter reader with active splitter"],
            [S("comment"), 2, "Licensed under CERN-OHL-P v2"],
            [S("comment"), 3, "Continues the P1-BASE by Research group Energy Transition, Windesheim"]],
           [S("lib_symbols")] + list(s.lib.values())] + s.items + [
           [S("sheet_instances"), [S("path"), "/", [S("page"), "1"]]]]
    out = os.path.join(PCB, PROJECT + ".kicad_sch")
    with open(out, "w", encoding="utf8", newline="\n") as f:
        f.write(dump(sch) + "\n")
    print("wrote", out)
    verify(out)


def verify(sch):
    """Export the netlist with kicad-cli and compare it with PARTS."""
    with tempfile.TemporaryDirectory() as tmp:
        net = os.path.join(tmp, "n.net")
        subprocess.run([CLI, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", net, sch], check=True,
                       capture_output=True)
        n = parse(open(net, encoding="utf8").read())
    got = {}
    for nt in find(first(n, "nets"), "net"):
        name = first(nt, "name")[1]
        nodes = frozenset((first(x, "ref")[1], first(x, "pin")[1]) for x in find(nt, "node"))
        got[name] = nodes
    want = collections.defaultdict(set)
    for p in PARTS:
        for pin, netname in p["nets"].items():
            if netname:
                want[netname if netname in POWER_NETS else "/" + netname].add((p["ref"], pin))
    errors = []
    for name, nodes in want.items():
        if got.get(name) != nodes:
            errors.append(f"{name}: drawing has {sorted(got.get(name, []))}, circuit wants {sorted(nodes)}")
    extra = [k for k, v in got.items() if k not in want and not k.startswith("unconnected-")]
    for k in extra:
        errors.append(f"unexpected net {k}: {sorted(got[k])}")
    if errors:
        raise SystemExit("netlist check FAILED:\n  " + "\n  ".join(errors))
    print(f"netlist check: {len(want)} nets equal to the circuit description")


if __name__ == "__main__":
    build()
