"""SPICE checks of the P1-BASE v3 circuit (ngspice, shipped with KiCad).

Run:  python tools/sim/run_sims.py      (needs numpy and matplotlib)
Writes plots and a summary to docs/simulation/.

The models are generic approximations (VDMOS/diode parameters close to the
datasheets, a behavioural Schmitt trigger). They are good enough to check
levels, timing margins and inrush, not to predict exact waveforms.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ngspice  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "docs", "simulation")
os.makedirs(OUT, exist_ok=True)

MODELS = """
.model N2N7002 VDMOS(Vto=1.8 Kp=0.25 Rd=1.2 Rs=0.3 Rg=10 Cgs=22p Cgdmax=12p Cgdmin=2p Cjo=15p Is=1e-14)
.model PAO3401 VDMOS(pchan Vto=-0.9 Kp=8 Rd=0.02 Rs=0.01 Rg=5 Cgs=550p Cgdmax=150p Cgdmin=40p Cjo=120p Is=1e-12)
.model DBAT54 D(Is=2e-7 N=1.04 Rs=2.5 Cjo=10p)
.model D5819 D(Is=3e-6 N=1.1 Rs=0.05 Cjo=110p)
.model DTVS D(Is=1e-12 N=1.2 Rs=0.2 Cjo=60p Bv=6.4 Ibv=1m)
.subckt LVC14 a y vcc
* behavioural Schmitt inverter: VT+ / VT- scale with VCC (typ. values TI SN74LVC1G14)
Bq yi 0 V = v(y) > v(vcc)/2 ? ( v(a) > 0.55*v(vcc) ? 0 : v(vcc) ) : ( v(a) < 0.33*v(vcc) ? v(vcc) : 0 )
Ro yi y 25
Co y 0 3p
Ci a 0 4p
.ends
"""

BAUD = 115200
TB = 1 / BAUD


def uart_pwl(byts, t0=20e-6, inverted=True, vhi=1.0):
    """PWL control voltage for the meter's output transistor: 1 = transistor on (line low)."""
    bits = []
    for b in byts:
        bits += [0] + [(b >> i) & 1 for i in range(8)] + [1]  # start, data LSB first, stop
    # idle = mark = 1. P1 is inverted: mark -> transistor ON -> line low
    pts = [(0, 1)]
    t = t0
    for bit in bits:
        on = bit if inverted else 1 - bit
        pts.append((t, pts[-1][1]))
        pts.append((t + 50e-9, on))
        t += TB
    pts.append((t + 20e-6, 1))
    s = " ".join(f"{p[0]:.9g} {p[1] * vhi:g}" for p in pts)
    return s, t + 20e-6


def sim_data_path():
    pwl, tend = uart_pwl([0x2F, 0x55])  # "/" starts a telegram, 0x55 = alternating bits
    results = {}
    cases = [("strong meter output (transistor 20 ohm)", "Rm mdrv 0 20", "1k", "50p"),
             ("weak meter output (opto, 4 mA, slow)", "Gm p1raw_m 0 cur='4m*v(ctl)'\nRm mdrv 0 1g", "1k", "50p"),
             ("strong meter, existing reader 10k pull-up, 2 m cable", "Rm mdrv 0 20", "10k", "100p")]
    fig, axs = plt.subplots(len(cases), 1, figsize=(10, 9), sharex=True)
    for ax, (label, meter, rpu_reader, ccable) in zip(axs, cases):
        weak = "opto" in label
        net = f"""* data path
{MODELS}
Vctl ctl 0 PWL({pwl})
V5 v5 0 4.7
{'* weak opto: current-limited sink with 2 us rise' if weak else ''}
{'Bdrv mdrv 0 V=0' if weak else 'Sm p1raw_m mdrv ctl 0 swm'}
{meter}
.model swm SW(Vt=0.5 Vh=0.1 Ron=1 Roff=1e9)
Ccab_m p1raw_m 0 50p
Rcab_m p1raw_m p1raw 0.2
Cesd3 p1raw 0 35p
R2 p1raw p1data 100
R3 p1data v5 1k
XU1 p1data splitdrv v5 LVC14
R4 splitdrv g13 4.7k
R32 g13 0 10k
Cg13 g13 0 6p
* LED1 + R7 load on U1 output
R7 v5 led1a 2.2k
DLED led1a splitdrv DLEDM
.model DLEDM D(Is=1e-20 N=1.8 Rs=10)
* splitter
M2 extfet splitdrv 0 N2N7002
R5 extfet extout 47
Cesd4 extout 0 35p
Rcab_r extout rdr 0.3
Ccab_r rdr 0 {ccable}
Rpu_r rdr vrdr {rpu_reader}
Vrdr vrdr 0 3.3
"""
        if weak:
            net = net.replace("Gm p1raw_m 0 cur='4m*v(ctl)'", "Bm p1raw_m 0 I=4m*v(ctlf)\nRf ctl ctlf 1k\nCf ctlf 0 2n")
        d = ngspice.run(net, f"tran 20n {tend:.6g}")
        t = d["time"] * 1e6
        ax.plot(t, d["p1raw"], label="P1 data at J2 pin 5", lw=0.9)
        ax.plot(t, d["g13"], label="G13 (ESP32 RX)", lw=0.9)
        ax.plot(t, d["rdr"], label="existing reader input (J3 pin 5)", lw=0.9)
        ax.set_title(label, fontsize=9)
        ax.set_ylabel("V")
        ax.grid(alpha=0.3)
        # timing: compare G13 edges to ideal bit edges
        results[label] = edge_stats(d["time"], d["g13"], d["rdr"], d["p1raw"])
    axs[0].legend(fontsize=7, loc="upper right")
    axs[-1].set_xlabel("time [µs]")
    fig.suptitle("P1 data path at 115 200 Bd: bytes 0x2F 0x55")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "data-path.png"), dpi=110)
    plt.close(fig)
    return results


def edge_stats(t, g13, rdr, raw):
    def widths(v, th):
        hi = v > th
        idx = np.nonzero(np.diff(hi.astype(int)))[0]
        if len(idx) < 3:
            return None
        w = np.diff(t[idx]) / TB
        return w
    w13 = widths(g13, 1.6)
    wr = widths(rdr, 1.65)
    out = {"min_low_P1_V": float(raw.min()), "G13_high_V": float(g13.max())}
    for name, w in (("G13", w13), ("reader", wr)):
        if w is None:
            out[name] = "no edges"
            continue
        err = np.abs(w - np.round(w)) * 100
        out[name + "_max_bit_error_pct"] = round(float(err.max()), 2)
    return out


def sim_request():
    rows = []
    cases = [
        ("DSMR 5, CoreInk requests (G26 high)", 5.0, 5.0, 3.3, 0.0),
        ("DSMR 5, existing reader requests", 5.0, 5.0, 0.0, 5.0),
        ("DSMR 5, both request", 5.0, 5.0, 3.3, 5.0),
        ("DSMR 5, nobody requests", 5.0, 5.0, 0.0, 0.0),
        ("DSMR 2/3, CoreInk on, requests", 0.0, 5.0, 3.3, 0.0),
        ("DSMR 2/3, CoreInk off, reader requests", 0.0, 0.0, 0.0, 5.0),
        ("DSMR 5, reader requests with weak 4.5 V output (1 k)", 5.0, 5.0, 0.0, 4.5),
    ]
    for label, vmeter, v5out, g26, vreq in cases:
        net = f"""* request
{MODELS}
Vm vmeter 0 {vmeter}
Vo c5vout 0 {v5out}
D2a vmeter v5 DBAT54
D2b c5vout v5 DBAT54
R21 vmeter g36 100k
R22 g36 0 68k
C3 v5 0 1u
Rload_v5 v5 0 20k
M3 metreq reqgate v5 PAO3401
R10 reqgate v5 100k
R20 v5 led2a 3.3k
DL2 led2a reqgate DLEDM
.model DLEDM D(Is=1e-20 N=1.8 Rs=10)
M4 reqgate reqen 0 N2N7002
Vg26 g26 0 {g26}
R11 g26 reqen 1k
R12 reqen 0 100k
Vrd rdrsrc 0 {vreq}
Rrd rdrsrc extreqraw 1k
R16 extreqraw extreq 100
R13 extreq extreqg 10k
R14 extreqg 0 100k
M5 reqgate extreqg 0 N2N7002
D7 extreq metreq D5819
R18 extreq g34 47k
R19 g34 0 68k
R9 metreq 0 100k
R8 metreq j2p2 100
* meter request input: 1 mA at 5 V
Rmeter j2p2 0 4.7k
"""
        d = ngspice.run(net, "op")
        rows.append((label, float(d["j2p2"][0]), float(d["g34"][0]), float(d["g36"][0])))
    return rows


def sim_softstart():
    net = f"""* charger soft start
{MODELS}
* meter supply: 5 V, 0.5 ohm
Vm vsrc 0 5
Rsrc vsrc vmeter 0.5
C1 vmeter 0 1u
C2 vmeter 0 100n
M6 chgin chggate vmeter PAO3401
R23 chggate vmeter 100k
C7 chggate chgin 22n
R24 chggate chgdrv 47k
M7 chgdrv chgen 0 N2N7002
Vg25 g25 0 PWL(0 0 1m 0 1.001m 3.3)
R25 g25 chgen 1k
R26 chgen 0 100k
C8 chgin 0 10u
* TP4056: draws 120 mA once its input is above 4 V
Bchg chgin 0 I = v(chgin) > 4.0 ? 0.12 : 0
"""
    d = ngspice.run(net, "tran 1u 8m")
    t = d["time"] * 1e3
    i = (5.0 - d["vmeter"]) / 0.5 * 1e3
    fig, ax = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
    ax[0].plot(t, d["vmeter"], label="VMETER")
    ax[0].plot(t, d["chgin"], label="CHG_IN")
    ax[0].set_ylabel("V"); ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3)
    ax[1].plot(t, i, color="C3", label="current from the meter")
    ax[1].axhline(260, color="k", ls="--", lw=0.8, label="DSMR 5 fold-back threshold (260 mA)")
    ax[1].set_ylabel("mA"); ax[1].set_xlabel("time [ms]"); ax[1].legend(fontsize=8); ax[1].grid(alpha=0.3)
    fig.suptitle("Switching on P1 charging (G25 high at 1 ms)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "charger-soft-start.png"), dpi=110)
    plt.close(fig)
    return float(i.max())


def sim_reversed():
    """Crossed cable: meter 5 V arrives on our pin 6 (GND), meter GND on our pin 1."""
    net = f"""* crossed cable, meter ground floats at -5 V relative to our ground
{MODELS}
Vm 0 mgnd 5
* our J2: pin1 <- meter GND, pin2 <- meter data (OC, on), pin5 <- meter request input (4.7k)
Rp1 mgnd j2p1 0.1
Moc j2p2 1 mgnd N2N7002
Voc 1 mgnd 5
Rreq j2p5 mgnd 4.7k
* our side, CoreInk on battery, 5V_OUT present
Vo c5vout 0 5
M1 j2p1 q1g vmeter PAO3401
R1 q1g 0 10k
D1 0 vmeter DTVS
C1 vmeter 0 1u
D2a vmeter v5 DBAT54
D2b c5vout v5 DBAT54
R21 vmeter g36 100k
R22 g36 0 68k
Desd5a j2p2 e5 DTVS
Desd5b 0 e5 DTVS
R8 j2p2 metreq 100
R9 metreq 0 100k
D7 extreq metreq D5819
R18 extreq g34 47k
R19 g34 0 68k
Desd3a j2p5 e3 DTVS
Desd3b 0 e3 DTVS
R2 j2p5 p1data 100
R3 p1data v5 1k
"""
    d = ngspice.run(net, "op")
    return {k: float(d[k][0]) for k in ("vmeter", "metreq", "p1data", "g36", "extreq") if k in d} | {
        "I_meter_mA": float(-d.get("vm#branch", [0])[0] * 1e3)}


def main():
    lines = ["# Simulation results", "",
             "Generated by `tools/sim/run_sims.py` with ngspice (KiCad 10). Generic models: check levels and margins, "
             "not exact waveforms.", ""]
    dp = sim_data_path()
    lines += ["## 1. Data path at 115 200 Bd", "", "![data path](data-path.png)", "",
              "| Case | Lowest level at J2 pin 5 [V] | G13 high [V] | Max bit-width error G13 [%] | Max bit-width error reader [%] |",
              "|---|---:|---:|---:|---:|"]
    for k, v in dp.items():
        lines.append(f"| {k} | {v['min_low_P1_V']:.2f} | {v['G13_high_V']:.2f} | {v.get('G13_max_bit_error_pct', v.get('G13'))} | "
                     f"{v.get('reader_max_bit_error_pct', v.get('reader'))} |")
    rq = sim_request()
    lines += ["", "## 2. Data request levels (DC)", "", "DSMR: the request must be ≥ 4.0 V to make the meter send.", "",
              "| Case | Request at meter (J2 pin 2) [V] | G34 [V] | G36 [V] |", "|---|---:|---:|---:|"]
    for label, vreq, g34, g36 in rq:
        lines.append(f"| {label} | {vreq:.2f} | {g34:.2f} | {g36:.2f} |")
    ipk = sim_softstart()
    lines += ["", "## 3. Switching on P1 charging", "", "![soft start](charger-soft-start.png)", "",
              f"Peak current drawn from the meter: **{ipk:.0f} mA** (DSMR 5 fold-back starts at 260 mA; "
              "the steady state is the 120 mA charge current plus the rest of the board)."]
    rv = sim_reversed()
    lines += ["", "## 4. Crossed (1-to-6) cable", "", "Meter powered, cable crossed, CoreInk on battery.", "",
              "| Node | Value |", "|---|---:|"]
    for k, v in rv.items():
        lines.append(f"| {k} | {v:.3f} |")
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("done")


if __name__ == "__main__":
    main()
