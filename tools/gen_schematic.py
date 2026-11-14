"""Generate the P1-BASE v3 schematic (pcb/needforheat-p1-base-hardware.kicad_sch).

The circuit is described as data (CIRCUIT below): every part with its symbol,
footprint, LCSC number and the net on each pin. The script places the parts
block by block and puts a net label on every pin, so the drawing and the
netlist always agree. Run with any Python 3:  python tools/gen_schematic.py
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import Sym as S, dump, find, first  # noqa: E402
import kicadlib  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(ROOT, "pcb")
PROJECT = "needforheat-p1-base-hardware"
CUSTOM_LIB = os.path.join(PCB, "p1base.kicad_sym")
NS = uuid.UUID("6f1c2b4e-6b0e-4c55-9d7a-1f2e3d4c5b6a")


def uid(*k):
    return str(uuid.uuid5(NS, "/".join(map(str, k))))


# --------------------------------------------------------------------------
# Custom symbols (written to pcb/p1base.kicad_sym)
# --------------------------------------------------------------------------
def _pin(typ, x, y, ang, name, num, length=2.54):
    font = [S("effects"), [S("font"), [S("size"), 1.27, 1.27]]]
    return [S("pin"), S(typ), S("line"), [S("at"), x, y, ang], [S("length"), length],
            [S("name"), name, font], [S("number"), num, font]]


def _prop(k, v, x, y, hide=False):
    eff = [S("effects"), [S("font"), [S("size"), 1.27, 1.27]]]
    if hide:
        eff.append([S("hide"), S("yes")])
    return [S("property"), k, v, [S("at"), x, y, 0], eff]


def _box_symbol(name, ref, value, fp, desc, left, right, top=(), bottom=(), w=10.16):
    """left/right: list of (num, name, type) from top to bottom."""
    n = max(len(left), len(right))
    h = 2.54 * (n + 1)
    y0 = h / 2
    pins = []
    for i, (num, nm, t) in enumerate(left):
        pins.append(_pin(t, -w / 2 - 2.54, round(y0 - 2.54 * (i + 1), 2), 0, nm, num))
    for i, (num, nm, t) in enumerate(right):
        pins.append(_pin(t, w / 2 + 2.54, round(y0 - 2.54 * (i + 1), 2), 180, nm, num))
    for i, (num, nm, t) in enumerate(top):
        pins.append(_pin(t, round(-2.54 * (len(top) - 1) / 2 + 2.54 * i, 2), y0 + 2.54, 270, nm, num))
    for i, (num, nm, t) in enumerate(bottom):
        pins.append(_pin(t, round(-2.54 * (len(bottom) - 1) / 2 + 2.54 * i, 2), -y0 - 2.54, 90, nm, num))
    body = [S("symbol"), name + "_0_1",
            [S("rectangle"), [S("start"), -w / 2, y0], [S("end"), w / 2, -y0],
             [S("stroke"), [S("width"), 0.254], [S("type"), S("default")]], [S("fill"), [S("type"), S("background")]]]]
    return [S("symbol"), name, [S("pin_names"), [S("offset"), 1.016]],
            [S("exclude_from_sim"), S("no")], [S("in_bom"), S("yes")], [S("on_board"), S("yes")],
            _prop("Reference", ref, 0, y0 + 1.27), _prop("Value", value, 0, -y0 - 1.27),
            _prop("Footprint", fp, 0, -y0 - 3.81, True), _prop("Datasheet", "", 0, 0, True),
            _prop("Description", desc, 0, 0, True),
            body, [S("symbol"), name + "_1_1"] + pins]


def write_custom_lib():
    tp = _box_symbol(
        "TP4056", "U", "TP4056", "Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm",
        "1 A linear Li-ion charger, charge current set by PROG (I = 1200 V / R_PROG)",
        left=[("4", "VCC", "power_in"), ("8", "CE", "input"), ("2", "PROG", "passive"), ("1", "TEMP", "input")],
        right=[("5", "BAT", "power_out"), ("7", "~{CHRG}", "open_collector"), ("6", "~{STDBY}", "open_collector")],
        bottom=[("3", "GND", "power_in"), ("9", "EP", "passive")], w=12.7)
    bus = _box_symbol(
        "CoreInk_Bus", "J", "CoreInk bus", "p1base:CoreInk_Bus_2x08_P2.54mm",
        "M5Stack CoreInk 2x8 back connector (CoreInk-Bus); pads named after the CoreInk signals",
        left=[("GND", "GND", "passive"), ("5VIN", "5V_IN", "passive"), ("RST", "EXT_RST", "passive"),
              ("G13", "G13", "passive"), ("G21", "G21/SDA", "passive"), ("G18", "G18/SCK", "passive"),
              ("G34", "G34 (in)", "passive"), ("G23", "G23/MOSI", "passive")],
        right=[("BAT", "BAT", "passive"), ("5VOUT", "5V_OUT", "passive"), ("3V3", "3V3", "passive"),
               ("G14", "G14", "passive"), ("G22", "G22/SCL", "passive"), ("G36", "G36 (in)", "passive"),
               ("G26", "G26", "passive"), ("G25", "G25", "passive")], w=15.24)
    lib = [S("kicad_symbol_lib"), [S("version"), 20231120], [S("generator"), "gen_schematic.py"],
           [S("generator_version"), "1.0"], tp, bus]
    with open(CUSTOM_LIB, "w", encoding="utf8", newline="\n") as f:
        f.write(dump(lib) + "\n")


# --------------------------------------------------------------------------
# The circuit
# --------------------------------------------------------------------------
R0603 = "Resistor_SMD:R_0603_1608Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SOT235 = "Package_TO_SOT_SMD:SOT-23-5"
LED0603 = "LED_SMD:LED_0603_1608Metric"
RJ = "Connector_RJ:RJ25_Wayconn_MJEA-660X1_Horizontal"
TP_FP = "TestPoint:TestPoint_Pad_D1.0mm"

RES_LCSC = {"0R": "C21189", "47R": "C23182", "100R": "C22775", "220R": "C22962", "1k": "C21190", "2k2": "C4190", "4k7": "C23162",
            "3k3": "C22978", "10k": "C25804", "20k": "C4184", "47k": "C25819", "68k": "C23231", "100k": "C25803"}


def R(ref, val, n1, n2, at, rot=0, dnp=False):
    return dict(ref=ref, lib="Device:R", value=val, fp=R0603, lcsc=RES_LCSC[val], at=at, rot=rot,
                nets={"1": n1, "2": n2}, dnp=dnp)


def C(ref, val, n1, n2, at, rot=0):
    lc = {"22n": ("C21122", C0603), "100n": ("C14663", C0603), "1u": ("C15849", C0603), "10u": ("C15850", C0805)}[val]
    return dict(ref=ref, lib="Device:C", value=val, fp=lc[1], lcsc=lc[0], at=at, rot=rot, nets={"1": n1, "2": n2})


def NMOS(ref, g, d, s, at, rot=0):
    return dict(ref=ref, lib="Transistor_FET:2N7002", value="2N7002", fp=SOT23, lcsc="C8545", at=at, rot=rot,
                nets={"1": g, "2": s, "3": d})


def PMOS(ref, g, d, s, at, rot=0):
    return dict(ref=ref, lib="Transistor_FET:AO3401A", value="AO3401A", fp=SOT23, lcsc="C15127", at=at, rot=rot,
                nets={"1": g, "2": s, "3": d})


def ESD(ref, line, at, rot=0):
    return dict(ref=ref, lib="Device:D_TVS", value="PESD5V0S1BB", fp="Diode_SMD:D_SOD-523", lcsc="C2687128",
                at=at, rot=rot, nets={"1": line, "2": "GND"})


def LED(ref, color, a, k, at, rot=0):
    lc = {"green": "C12624", "yellow": "C2287", "red": "C2286"}[color]
    return dict(ref=ref, lib="Device:LED", value=f"LED {color}", fp=LED0603, lcsc=lc, at=at, rot=rot,
                nets={"2": a, "1": k})


def TP(ref, net, at):
    return dict(ref=ref, lib="Connector:TestPoint", value=net, fp=TP_FP, lcsc="", at=at, rot=0, nets={"1": net},
                bom=False)


def LVC14(ref, a, y, vcc, at):
    return dict(ref=ref, lib="74xGxx:74LVC1G14", value="74LVC1G14", fp=SOT235, lcsc="C7835", at=at, rot=0,
                nets={"1": None, "2": a, "3": "GND", "4": y, "5": vcc})


def PWR(net, at):
    return dict(ref="#FLG", lib="power:PWR_FLAG", value="PWR_FLAG", fp="", lcsc="", at=at, rot=0, nets={"1": net},
                power=True)


# Blocks: (title, origin, parts). Coordinates in mm on an A3 sheet; parts are
# placed relative to the block origin.
def circuit():
    B = []
    # 1. Connectors -------------------------------------------------------
    B.append(("1  Connectors", (25.4, 30.48), [
        dict(ref="J2", lib="Connector:6P6C", value="RJ12 to meter", fp=RJ, lcsc="C77859", at=(10.16, 12.7), rot=0,
             nets={"1": "P1_5V", "2": "METER_REQ_RAW", "3": "GND", "4": None, "5": "P1_DATA_RAW", "6": "GND"}),
        dict(ref="J3", lib="Connector:6P6C", value="RJ12 existing reader", fp=RJ, lcsc="C77859", at=(10.16, 45.72),
             rot=0, nets={"1": "VMETER", "2": "EXT_REQ_RAW", "3": "GND", "4": None, "5": "EXT_DATA_OUT", "6": "GND"}),
        dict(ref="J1", lib="p1base:CoreInk_Bus", value="CoreInk bus", fp="p1base:CoreInk_Bus_2x08_P2.54mm",
             lcsc="C72555", at=(20.32, 88.9), rot=0,
             nets={"GND": "GND", "BAT": "COREINK_BAT", "5VIN": None, "5VOUT": "COREINK_5VOUT", "RST": None,
                   "3V3": None, "G13": "G13_RX", "G14": "G14_CHGHI", "G21": None, "G22": None, "G18": None,
                   "G36": "G36_VMETER", "G34": "G34_EXTREQ", "G26": "G26_REQ", "G23": None, "G25": "G25_CHG"}),
    ]))
    # 2. Meter power: reverse protection, TVS, 5 V OR ------------------------
    B.append(("2  Meter 5 V, protection, V5", (88.9, 30.48), [
        PMOS("Q1", "Q1_G", "P1_5V", "VMETER", (12.7, 10.16), rot=90),
        R("R1", "10k", "Q1_G", "GND", (10.16, 25.4)),
        dict(ref="D1", lib="Device:D_Zener", value="SMF5.0A", fp="Diode_SMD:D_SMF", lcsc="C193402", at=(35.56, 20.32),
             rot=90, nets={"1": "VMETER", "2": "GND"}),
        C("C1", "1u", "VMETER", "GND", (45.72, 20.32)),
        C("C2", "100n", "VMETER", "GND", (53.34, 20.32)),
        dict(ref="D2", lib="Diode:BAT54C", value="BAT54C", fp=SOT23, lcsc="C37704", at=(20.32, 45.72), rot=0,
             nets={"1": "VMETER", "2": "COREINK_5VOUT", "3": "V5"}),
        C("C3", "1u", "V5", "GND", (45.72, 45.72)),
        R("R21", "100k", "VMETER", "G36_VMETER", (60.96, 40.64)),
        R("R22", "68k", "G36_VMETER", "GND", (60.96, 53.34)),
        C("C6", "100n", "G36_VMETER", "GND", (71.12, 53.34)),
        PWR("VMETER", (30.48, 5.08)), PWR("V5", (33.02, 38.1)), PWR("GND", (53.34, 30.48)),
    ]))
    # 3. Data in + active splitter ----------------------------------------
    B.append(("3  P1 data in, Schmitt trigger, active splitter", (175.26, 30.48), [
        ESD("D3", "P1_DATA_RAW", (5.08, 20.32), rot=90),
        R("R2", "100R", "P1_DATA_RAW", "P1_DATA", (17.78, 12.7), rot=90),
        R("R3", "1k", "P1_DATA", "V5", (30.48, 2.54)),
        LVC14("U1", "P1_DATA", "SPLIT_DRV", "V5", (53.34, 15.24)),
        C("C4", "100n", "V5", "GND", (76.2, 2.54)),
        R("R4", "4k7", "SPLIT_DRV", "G13_RX", (86.36, 50.8), rot=90),
        R("R32", "10k", "G13_RX", "GND", (96.52, 58.42)),
        NMOS("Q2", "SPLIT_DRV", "EXT_DATA_FET", "GND", (96.52, 17.78)),
        R("R5", "47R", "EXT_DATA_FET", "EXT_DATA_OUT", (106.68, 5.08), rot=90),
        R("R6", "10k", "EXT_DATA_OUT", "V5", (119.38, 2.54), dnp=True),
        ESD("D4", "EXT_DATA_OUT", (119.38, 20.32), rot=90),
        R("R7", "2k2", "V5", "LED1_A", (78.74, 22.86)),
        LED("LED1", "green", "LED1_A", "SPLIT_DRV", (78.74, 33.02), rot=90),
        
    ]))
    # 4. Data request ------------------------------------------------------
    B.append(("4  Data request: OR of CoreInk (G26) and existing reader",
              (25.4, 165.1), [
        ESD("D5", "METER_REQ_RAW", (5.08, 20.32), rot=90),
        R("R8", "100R", "METER_REQ_RAW", "METER_REQ", (17.78, 12.7), rot=90),
        R("R9", "100k", "METER_REQ", "GND", (30.48, 25.4)),
        PMOS("Q3", "REQ_GATE", "METER_REQ", "V5", (45.72, 7.62), rot=0),
        R("R10", "100k", "REQ_GATE", "V5", (33.02, 0)),
        NMOS("Q4", "REQ_EN", "REQ_GATE", "GND", (58.42, 25.4)),
        R("R11", "1k", "G26_REQ", "REQ_EN", (66.04, 40.64), rot=90),
        R("R12", "100k", "REQ_EN", "GND", (53.34, 45.72)),
        NMOS("Q5", "EXT_REQ_G", "REQ_GATE", "GND", (86.36, 25.4)),
        R("R13", "10k", "EXT_REQ", "EXT_REQ_G", (93.98, 40.64), rot=90),
        R("R14", "100k", "EXT_REQ_G", "GND", (81.28, 45.72)),
        R("R15", "0R", "REQ_GATE", "GND", (106.68, 25.4), dnp=True),
        ESD("D6", "EXT_REQ_RAW", (121.92, 55.88), rot=90),
        R("R16", "100R", "EXT_REQ_RAW", "EXT_REQ", (132.08, 48.26), rot=90),
        dict(ref="D7", lib="Diode:1N5819WS", value="1N5819WS", fp="Diode_SMD:D_SOD-323", lcsc="C191023",
             at=(144.78, 35.56), rot=90, nets={"2": "EXT_REQ", "1": "METER_REQ"}),
        R("R18", "47k", "EXT_REQ", "G34_EXTREQ", (157.48, 48.26), rot=90),
        R("R19", "68k", "G34_EXTREQ", "GND", (167.64, 58.42)),
        R("R20", "3k3", "V5", "LED2_A", (124.46, 10.16)),
        LED("LED2", "yellow", "LED2_A", "REQ_GATE", (124.46, 20.32), rot=90),
    ]))
    # 5. Charger -------------------------------------------------------------
    B.append(("5  P1 charging of the CoreInk battery (G25 on, G14 60/120 mA)",
              (215.9, 165.1), [
        PMOS("Q6", "CHG_GATE", "CHG_IN", "VMETER", (20.32, 7.62), rot=90),
        R("R23", "100k", "CHG_GATE", "VMETER", (5.08, 20.32)),
        C("C7", "22n", "CHG_GATE", "CHG_IN", (12.7, 30.48)),
        R("R24", "47k", "CHG_GATE", "CHG_GATE_DRV", (22.86, 25.4)),
        NMOS("Q7", "CHG_EN", "CHG_GATE_DRV", "GND", (20.32, 40.64)),
        R("R25", "1k", "G25_CHG", "CHG_EN", (5.08, 50.8), rot=90),
        R("R26", "100k", "CHG_EN", "GND", (15.24, 58.42)),
        C("C8", "10u", "CHG_IN", "GND", (40.64, 20.32)),
        dict(ref="U3", lib="p1base:TP4056", value="TP4056", fp="Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm",
             lcsc="C16581", at=(71.12, 25.4), rot=0,
             nets={"4": "CHG_IN", "8": "CHG_IN", "2": "PROG", "1": "GND", "5": "COREINK_BAT", "7": "CHRG_N",
                   "6": None, "3": "GND", "9": "GND"}),
        R("R27", "20k", "PROG", "GND", (50.8, 45.72)),
        R("R28", "20k", "PROG", "PROG_HI", (63.5, 50.8), rot=90),
        NMOS("Q8", "CHG_HI", "PROG_HI", "GND", (76.2, 55.88)),
        R("R29", "1k", "G14_CHGHI", "CHG_HI", (88.9, 66.04), rot=90),
        R("R30", "100k", "CHG_HI", "GND", (68.58, 71.12)),
        C("C9", "10u", "COREINK_BAT", "GND", (106.68, 30.48)),
        R("R31", "2k2", "CHG_IN", "LED3_A", (99.06, 2.54)),
        LED("LED3", "red", "LED3_A", "CHRG_N", (99.06, 15.24), rot=90),
        PWR("CHG_IN", (35.56, 2.54)),
    ]))
    # 6. Test points --------------------------------------------------------
    B.append(("6  Test points", (330.2, 30.48), [
        TP("TP1", "VMETER", (0, 10.16)), TP("TP2", "V5", (12.7, 10.16)), TP("TP3", "P1_DATA", (25.4, 10.16)),
        TP("TP4", "METER_REQ", (0, 25.4)), TP("TP5", "EXT_DATA_OUT", (12.7, 25.4)),
        TP("TP6", "CHG_IN", (25.4, 25.4)), TP("TP7", "GND", (0, 40.64)),
    ]))
    B.append(("7  Enclosure peg holes", (330.2, 160.02), [
        dict(ref=f"H{i}", lib="Mechanical:MountingHole", value="Peg hole 2.2 mm",
             fp="MountingHole:MountingHole_2.2mm_M2", lcsc="", at=(12.7 * (i - 1), 0), rot=0, nets={}, bom=False)
        for i in (1, 2, 3)]))
    return B


# --------------------------------------------------------------------------
# Schematic writer
# --------------------------------------------------------------------------
def rot_pt(x, y, rot):
    # symbol coords are y-up; schematic y-down. rotation counter-clockwise in symbol space.
    if rot == 0:
        return x, y
    if rot == 90:
        return -y, x
    if rot == 180:
        return -x, -y
    if rot == 270:
        return y, -x
    raise ValueError(rot)


def snap(v):
    return round(round(v / 1.27) * 1.27, 2)


def font(size=1.27, **kw):
    e = [S("effects"), [S("font"), [S("size"), size, size]]]
    for k, v in kw.items():
        if k == "justify":
            e.append([S("justify")] + [S(x) for x in v.split()])
        if k == "hide" and v:
            e.append([S("hide"), S("yes")])
    return e


def build():
    write_custom_lib()
    extra = {"p1base": CUSTOM_LIB}
    blocks = circuit()
    sch_uuid = uid("sheet")
    lib_syms, items = {}, []
    nets_seen = {}
    flg = 0
    for title, (ox, oy), parts in blocks:
        items.append([S("text"), title, [S("exclude_from_sim"), S("no")], [S("at"), ox, oy - 7.62, 0],
                      font(2.0, justify="left bottom"), [S("uuid"), uid("blk", title)]])
        for p in parts:
            lid = p["lib"]
            if lid not in lib_syms:
                lib_syms[lid] = kicadlib.load_symbol(lid, extra)
            sym = lib_syms[lid]
            X, Y = snap(ox + p["at"][0]), snap(oy + p["at"][1])
            rot = p.get("rot", 0)
            ref = p["ref"]
            if p.get("power"):
                flg += 1
                ref = f"#FLG0{flg:02d}"
            props = []
            if lid.startswith("Transistor_FET"):
                rpos, vpos = (X + 5.08, Y - 1.27), (X + 5.08, Y + 1.27)
            elif rot in (90, 270) and lid.startswith("Device:"):
                rpos, vpos = (X - 1.27, Y - 2.54), (X - 1.27, Y + 3.81)
            else:
                rpos, vpos = (X + 2.54, Y - 1.27), (X + 2.54, Y + 1.27)
            fields = [("Reference", ref, rpos, False), ("Value", p["value"], vpos, p.get("power", False)),
                      ("Footprint", p["fp"], (X, Y), True), ("Datasheet", "", (X, Y), True)]
            if p.get("lcsc"):
                fields.append(("LCSC", p["lcsc"], (X, Y), True))
            for k, v, (px, py), hide in fields:
                props.append([S("property"), k, v, [S("at"), px, py, 0], font(hide=hide, justify="left")])
            pin_uuids = []
            for pin in kicadlib.pins(sym):
                if pin["unit"] not in (0, 1):
                    continue
                pin_uuids.append([S("pin"), pin["number"], [S("uuid"), uid(ref, "pin", pin["number"])]])
                dx, dy = rot_pt(pin["x"], pin["y"], rot)
                px, py = snap(X + dx), snap(Y - dy)
                ang = (pin["angle"] + rot) % 360
                net = p["nets"].get(pin["number"], "__missing__")
                if net == "__missing__":
                    raise SystemExit(f"{ref}: pin {pin['number']} has no net assignment")
                if p.get("power"):
                    # PWR_FLAG: attach with a label on its pin
                    net = p["nets"]["1"]
                if net is None:
                    items.append([S("no_connect"), [S("at"), px, py], [S("uuid"), uid(ref, "nc", pin["number"])]])
                    continue
                nets_seen.setdefault(net, []).append(f"{ref}.{pin['number']}")
                lang = (ang + 180) % 360
                just = {0: "left", 180: "right", 90: "left", 270: "right"}[lang]
                items.append([S("label"), net, [S("at"), px, py, lang], font(1.0, justify=just + " bottom"),
                              [S("uuid"), uid(ref, "lbl", pin["number"])]])
            inst = [S("instances"), [S("project"), PROJECT,
                                      [S("path"), "/" + sch_uuid, [S("reference"), ref], [S("unit"), 1]]]]
            dnp = bool(p.get("dnp"))
            in_bom = p.get("bom", True) and not p.get("power") and not dnp
            items.append([S("symbol"), [S("lib_id"), lid], [S("at"), X, Y, rot], [S("unit"), 1],
                          [S("exclude_from_sim"), S("no")], [S("in_bom"), S("yes" if in_bom else "no")],
                          [S("on_board"), S("no" if p.get("power") else "yes")], [S("dnp"), S("yes" if dnp else "no")],
                          [S("uuid"), uid(ref, "sym")]] + props + pin_uuids + [inst])
    # sanity: every net needs >= 2 connections, except test/flag only nets
    single = {n: v for n, v in nets_seen.items() if len(v) < 2}
    if single:
        raise SystemExit(f"nets with a single connection: {single}")
    notes = [
        "NeedForHeat P1-BASE v3.0 - design rationale in docs/design-v3.md",
        "Firmware interface: G13 = P1 RX (not inverted); G26 = data request (high = request);",
        "G25 = P1 charging on (high); G14 = charge current 120 mA (high) / 60 mA (low);",
        "G36 = meter 5 V via 100k/68k (x0.405); G34 = existing reader requests (47k/68k).",
        "DNP: R6 = pull-up for readers without own pull-up; R15 = always request data.",
    ]
    for i, t in enumerate(notes):
        items.append([S("text"), t, [S("exclude_from_sim"), S("no")], [S("at"), 25.4, 254.0 + 5.08 * i, 0],
                      font(1.5, justify="left bottom"), [S("uuid"), uid("note", i)]])
    sch = [S("kicad_sch"), [S("version"), 20231120], [S("generator"), "eeschema"], [S("generator_version"), "8.0"],
           [S("uuid"), sch_uuid], [S("paper"), "A3"],
           [S("title_block"), [S("title"), "NeedForHeat P1-BASE"], [S("date"), "2026-11-13"], [S("rev"), "3.0"],
            [S("company"), "energiegedrag.nl"],
            [S("comment"), 1, "M5Stack CoreInk extension: P1 smart meter reader with active splitter"],
            [S("comment"), 2, "Licensed under CERN-OHL-P v2"],
            [S("comment"), 3, "Continues the P1-BASE by Research group Energy Transition, Windesheim"]],
           [S("lib_symbols")] + list(lib_syms.values())] + items + [
           [S("sheet_instances"), [S("path"), "/", [S("page"), "1"]]]]
    out = os.path.join(PCB, PROJECT + ".kicad_sch")
    with open(out, "w", encoding="utf8", newline="\n") as f:
        f.write(dump(sch) + "\n")
    print("wrote", out, "nets:", len(nets_seen))


if __name__ == "__main__":
    build()
