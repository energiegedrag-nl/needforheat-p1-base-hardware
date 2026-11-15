# P1-BASE v3.0 – design <!-- omit in toc -->

This document records the requirements, architecture, calculations and design decisions for version 3.0 of the NeedForHeat P1-BASE: an extension module (BASE) for the back of an [M5Stack CoreInk](https://docs.m5stack.com/en/core/coreink) that reads Dutch smart meters via the [P1 port](https://github.com/energiegedrag-nl/dsmr-info) and passes the P1 signal on to an existing P1 reader.

> Status: **design, not yet built or tested.** Every value marked *verify* must be checked on a first prototype.

## Table of contents <!-- omit in toc -->
- [1. Requirements](#1-requirements)
- [2. What changed since v2.7](#2-what-changed-since-v27)
- [3. Architecture](#3-architecture)
- [4. Circuit blocks](#4-circuit-blocks)
  - [4.1 Meter connection and protection](#41-meter-connection-and-protection)
  - [4.2 Data input](#42-data-input)
  - [4.3 Active splitter](#43-active-splitter)
  - [4.4 Data request](#44-data-request)
  - [4.5 Power from the P1 port](#45-power-from-the-p1-port)
  - [4.6 Indicators and test points](#46-indicators-and-test-points)
  - [4.7 LED dimmer](#47-led-dimmer)
- [5. Firmware interface](#5-firmware-interface)
- [6. Calculations](#6-calculations)
- [7. Mechanics](#7-mechanics)
- [8. Production](#8-production)
- [9. Design decisions](#9-design-decisions)
- [9a. Redesign in progress](#9a-redesign-in-progress)
- [10. Open points to verify](#10-open-points-to-verify)
- [11. Out of scope](#11-out-of-scope)
- [12. Independent checks](#12-independent-checks)
- [13. Schematic drawing conventions](#13-schematic-drawing-conventions)

## 1. Requirements

From the [NeedForHeat DataGear paper](https://doi.org/10.48550/arXiv.2509.06927) (section II and VIII.A) and the design brief:

| # | Requirement |
|---|---|
| R1 | Read all P1 ports of DSMR 2.x to 5.x, including the Landis+Gyr E350/E360 series and meters with a push-pull data output. |
| R2 | An existing P1 reader of the household keeps working (integrated splitter), also when the CoreInk is off, asleep or crashed. |
| R3 | No DIP switches: the data request is managed by firmware, while an existing reader can always request data itself. |
| R4 | Use the power of DSMR ≥ 4 meters for the CoreInk without ever tripping the meter's fold-back protection; mains power stays optional. |
| R5 | Survive installation mistakes: a crossed (1-to-6) RJ12 cable or cables in the wrong socket must not damage anything, and the firmware must be able to tell what is wrong. |
| R6 | Pure extension of the M5Stack CoreInk; it cannot be mounted the wrong way round. |
| R7 | Fully assembled by JLCPCB: no hand soldering in production; basic parts where possible. |
| R8 | Fits the cost targets of DataGear (all devices per home < €250, ideally < €100); the BASE alone ships in a PostNL letterbox parcel. |
| R9 | Open hardware (CERN-OHL-P v2), reproducible from the files in this repository. |

## 2. What changed since v2.7

| Topic | v2.7 (2024) | v3.0 |
|---|---|---|
| Data input | 1 kΩ pull-up to ~4.7 V, 74HC14, 1k/2k2 divider to G13 | Same pull-up and supply; one single-gate 74LVC1G14 that feeds both the splitter and, through a 4k7/10k divider, G13 |
| Splitter output | Optocoupler EL357N (too slow for 115 200 Bd; Q3 option footprint did not match) | Open-drain 2N7002 driven by a Schmitt trigger, powered by the meter |
| Data request | 3 DIP switches, OR via Schottky diodes (~4.3 V left) | PMOS high-side switch (~4.7 V), switched by G26 and/or by the existing reader; passive diode path as fallback; firmware can read whether the reader requests |
| Power | CoreInk only on USB | Firmware-controlled 60/120 mA charging of the CoreInk battery from the meter (TP4056), soft start |
| Protection | none | Reverse-polarity PMOS, TVS on meter 5 V, ESD diodes and series resistors on all P1 signal lines |
| Monitoring | none | ADC on meter 5 V (G36), digital/ADC read-back of the external request (G34), three LEDs visible at the top edge and dimmable from firmware, test points |
| Mechanics | 2x8 header on the bottom (hand soldering), board 51 x 36 mm | Stacking header from the top (JLC THT), board 40 x 56 mm like the CoreInk, enclosure (*kuip*) that keys the CoreInk |

## 3. Architecture

```
            J2 (to meter)                                   J3 (existing reader)
   pin1 5V ─► Q1 reverse prot ─► VMETER ───────────────────► pin1 5V
                                   │  ├─► TVS D1
                                   │  ├─► R21/R22 ─► G36 (ADC)
                                   │  ├─► Q6 soft-start ─► TP4056 ─► CoreInk BAT   (G25 on, G14 60/120 mA)
                                   └─┬─ BAT54C ◄─ CoreInk 5V_OUT
                                     V5 (≈4.7 V)
   pin5 data ─► R2 ─► P1_DATA ─ 1k to V5
                         └─► U1 74LVC1G14 @V5 ─┬─► Q2 2N7002 ─► R5 ─► pin5 data
                                                └─► R4/R32 4k7/10k ─► G13 (UART RX)
   pin2 req ◄─ R8 ◄─ METER_REQ ◄─ Q3 PMOS from V5 ◄─ (Q4: G26) OR (Q5: reader req)
                         ▲                                            │
                         └──────── D7 Schottky (passive path) ◄── pin2 req ─► G34
```

The splitter and the request OR run from the meter's own 5 V, so the existing reader works independently of the CoreInk (R2). For DSMR 2/3 meters, which supply no power, `V5` comes from the CoreInk's `5V_OUT` and the reader's request still reaches the meter through D7.

## 4. Circuit blocks

### 4.1 Meter connection and protection

* **Q1 (AO3401A)**, a P-channel MOSFET in the supply line with its gate to GND, passes the meter's 5 V with almost no drop and blocks it when the cable is crossed (meter 5 V on our pin 6).
* **D1 (SMF5.0A)** clamps transients on `VMETER`; it sits behind Q1 so it never conducts a reversed supply.
* **D3, D4, D5, D6 (PESD5V0S1BB, bidirectional)** protect the four P1 signal lines; bidirectional because a crossed cable can pull a line below our ground. **100 Ω series resistors** (R2, R8, R16) limit the current in any fault.
* J3 pin 1 is fed from `VMETER` (after Q1), as with a passive splitter.

### 4.2 Data input

* **R3 1 kΩ to V5** is the pull-up of the meter's open-collector output: 5 mA at most (DSMR allows 30 mA). The low RC time constant was the key to reading Landis+Gyr E350/E360 meters in the 2024 lab tests with the v2.7 front end, so v3 keeps it.
* **U1 74LVC1G14 at V5 (≈ 4.7 V)** squares the signal up. Its thresholds at this supply (V<sub>T−</sub> ≈ 1.0–2.0 V) match the 74HC14 of v2.7, which read the Landis+Gyr meters in the lab. An earlier draft of v3 used a second 74LVC1G14 at 3.3 V for the ESP32; its lower V<sub>T−</sub> (≈ 0.6–1.2 V) would have demanded a lower low level from weak meter outputs, so it was dropped.
* **R4/R32 (4k7/10k)** divide the 4.7 V output to 3.2 V for G13 (input capacitance ≈ 5 pF: τ ≈ 16 ns). The divider draws 0.3 mA from V5 when the line is idle.
* The P1 line is inverted (idle = low); one inverter makes it a normal UART signal: **firmware must not invert RX** (unlike the old P1 gateway).
* Meters with a push-pull output above 4 V (seen on Kaifa E0009, Iskra ME382, Kamstrup 162JxC) are harmless: the line only meets LVC inputs, the pull-up and an ESD diode.

### 4.3 Active splitter

* **U1** also drives **Q2 (2N7002)**, an open-drain output to J3 pin 5. Two inversions: J3 pin 5 follows the meter's line exactly, as an open collector, as DSMR prescribes. The existing reader supplies its own pull-up (DSMR).
* A 2N7002 switches in tens of nanoseconds; at 115 200 Bd a bit lasts 8.7 µs. The edges at J3 are set by the reader's own pull-up and cable.
* **R6 (10 kΩ, not fitted)** is a pull-up for readers that do not have one.
* **LED1 (green)** blinks with the data on the splitter path, so data activity is visible without the CoreInk.

### 4.4 Data request

* **Q3 (AO3401A)** switches `V5` (≈ 4.7 V, DSMR requires ≥ 4.0 V) onto the meter's request line. Its gate is pulled low by **Q4** (firmware, G26 high) or **Q5** (the existing reader drives its request high). R9 (100 kΩ) keeps the line low when nobody requests; it is kept high-ohmic so it hardly loads the passive path below.
* **D7 (1N5819WS)** passes the reader's request straight to the meter. This path needs no power on the BASE at all, which matters for DSMR 2/3 meters with the CoreInk off. It costs one Schottky drop (≈ 0.35 V): a reader with a stiff 5 V request output still delivers ≈ 4.6 V; a reader whose request output has ≈ 1 kΩ source resistance ends up at ≈ 3.2 V (simulated), below the 4.0 V DSMR asks for. With the CoreInk on, the active path (Q5 → Q3) restores the full level, so this only matters for DSMR 2/3 meters with the CoreInk switched off.
* **G34** reads, through a 47k/68k divider, whether the existing reader requests data. Because D7 blocks in the other direction, our own request never shows up here.
* **Always-on request**: firmware can keep G26 high (also in deep sleep, with GPIO hold). **R15 (0 Ω, not fitted)** forces it in hardware; this is an assembly variant, not a solder job.
* **LED2 (yellow)** sits between V5 and the gate of Q3, so it lights exactly when Q3 drives the request line. It is never connected to the cable, so a crossed cable cannot reverse-bias it (LEDs only withstand ≈ 5 V reverse).

### 4.5 Power from the P1 port

DSMR limits: DSMR 2/3 no supply; DSMR 4.x 100 mA; DSMR 5.x 250 mA continuous, fold-back between 260 and 300 mA. The meter shares this with the existing reader.

* Instead of feeding the CoreInk's 5 V input (whose current we cannot limit and which could feed USB power back into the meter), v3 **charges the CoreInk battery directly** through its `BAT` pin with a **TP4056** linear charger. The battery buffers the Wi-Fi current peaks; the meter only ever sees the constant charge current.
* **G14** chooses the current: 60 mA (R27 20 kΩ) or 120 mA (R27 ∥ R28 = 10 kΩ, via Q8).
* **Q6 (AO3401A)** switches the charger on (**G25** high via Q7). C7 (22 nF, gate to drain) and R24 (47 kΩ) form a Miller soft start: the output rises at ≈ 3–4 V/ms, so the 10 µF input capacitor draws only ≈ 35 mA extra. Simulated peak from the meter: 152 mA (limit 260 mA). An earlier gate-source RC gave 382 mA and was replaced.
* Default after reset: off (pull-downs on G25 and G14). Suggested firmware policy: only enable after the P1 telegram shows DSMR ≥ 5; start at 60 mA; go to 120 mA only when `VMETER` stays above 4.75 V; back off when it sags.
* The TP4056 blocks reverse current (< 2 µA from the battery when the meter supply is absent), so the BASE never feeds the meter. When USB is connected, the CoreInk's own charger and the TP4056 both regulate to 4.2 V; that is harmless.
* **LED3 (red)** is on while the TP4056 charges.

### 4.6 Indicators and test points

| LED | Colour | On when | Current (full brightness) |
|---|---|---|---|
| LED1 | green | data bits on the P1 line | ≈ 1 mA while blinking |
| LED2 | yellow | data request active | ≈ 0.8 mA |
| LED3 | red | battery being charged from the P1 port | ≈ 1.3 mA |

The LEDs are side-looking parts (Lite-On LTST-S220KGKT / KSKT / KRKT, one package for all three colours) on the top
edge of the board, left of the meter socket (seen from the back). They shine through three windows in the top wall of the
tray, so they are visible from above, also when a BatteryBASE covers the lid. All three anode resistors are fed from
`VLED`, the dimmed supply (§ 4.7); the circuits above still decide *when* each LED is on.

Test points: TP1 `VMETER`, TP2 `V5`, TP3 `P1_DATA`, TP4 `METER_REQ`, TP5 `EXT_DATA_OUT` (splitter output), TP6 `CHG_IN`, TP7 GND.

### 4.7 LED dimmer

A blinking LED can disturb people when the meter is not in a closed meter cupboard, so the firmware can dim the three LEDs
or switch them off (one setting for all three).

* **No free GPIO** is left on the CoreInk bus (G18/G23 are the e-paper SPI lines), so the dimmer sits on the **I²C bus
  G21/G22**, which the CoreInk shares with its RTC (BM8563 at 0x51).
* **U5 (PCA9633DP1, C88381)** is a 4-channel I²C LED driver (8-pin version: fixed address 0x62). Only LED0 is used, with
  its **group PWM at 190 Hz**; LED1–LED3 are not connected.
* **U6 (XC6206P332MR, C5446)** powers U5 with 3.3 V from `V5`. The NeedForHeat firmware switches the CoreInk off
  completely between measurements (RTC wake-up), which also removes its 3V3; powered from the meter side, U5 keeps its
  setting. 3.3 V also matches the CoreInk's I²C levels (U5's input high is 0.7 × VDD). U6 draws ≈ 1 µA.
* **Q10 (2N7002) and Q9 (AO3401A)** switch `VLED`: U5's LED0 output pulls the gate of Q10 low to switch the LEDs off;
  R34 (100 k to 3.3 V) pulls it high otherwise, so **after power-up, before any firmware has set up U5, the LEDs are at
  full brightness** and work as before. R33 (100 k) keeps Q9 off while Q10 is off. At 190 Hz the 100 k gate resistors
  are fast enough (RC ≈ 65 µs against a 5.3 ms period).
* No pull-ups on our side: the CoreInk has them, to its own 3V3. When the CoreInk is off, U5 only sees low lines and
  drives nothing, so no current flows into the CoreInk (*verify* the pull-ups on the CoreInk schematic).
* Without the meter's 5 V (DSMR 2/3) `V5` comes from the CoreInk, so U5 is powered while the CoreInk is on and starts
  again at full brightness after the CoreInk was off.

Firmware recipe (register numbers from the PCA9633 datasheet, *verify* before use; write once after power-up of the
P1-BASE, the setting stays until the meter supply is lost):

| Register | Value | Meaning |
|---|---|---|
| MODE1 (0x00) | 0x00 | normal mode (wake from sleep; wait 500 µs) |
| MODE2 (0x01) | 0x14 | INVRT = 1 (output high = LEDs on), OUTDRV = 1 (totem pole), DMBLNK = 0 (group dimming) |
| PWM0 (0x02) | 0xFF | channel 0 fully on; the group PWM sets the brightness |
| GRPPWM (0x06) | 0–255 | brightness: duty cycle of `VLED` at 190 Hz |
| LEDOUT (0x08) | 0x03 / 0x01 / 0x00 | LDR0 = 11: dimmed by GRPPWM; 01: full brightness; 00: LEDs off |

A P1-BASE without the dimmer does not acknowledge address 0x62, so the firmware can tell the versions apart.

**Variant without dimming (U5 not placed).** The dimmer is built so that it can be left out by a BOM change only, with
the same board, layout and stencil:

* Mark **U5 as "do not place"** (remove it from the BOM and CPL, or deselect it in the JLCPCB BOM step).
* **Keep U6, C11, C12, R34, Q10, Q9 and R33** (all basic parts, a few cents). With U5 absent, R34 holds `LED_DIM` at
  3.3 V, so Q10 and Q9 are on and `VLED` = `V5`: the LEDs are at full brightness, as before the dimmer.
* Do **not** leave out U6: without it R34 has no supply, Q10 stays off and the LEDs never light.
* The firmware finds no device at 0x62 and skips the LED settings; nothing else on G21/G22 changes.
* Saving (quote of 15 November 2026): the PCA9633 (≈ € 2.80 per board at 5 pieces) and one extended-part fee
  (≈ € 2.80 per order). It also removes the only part that talks on the CoreInk's I²C bus, shared with its RTC.

The first prototype order keeps U5, to learn whether dimming is wanted and whether the I²C control works.

## 5. Firmware interface

| CoreInk pin | Direction | Function | Notes |
|---|---|---|---|
| G13 | in | P1 data (UART RX) | not inverted; 115 200 8N1 (DSMR ≥ 4) or 9600 7E1 (DSMR 2/3) |
| G26 | out | data request | high = request; pull-down on the BASE |
| G25 | out | P1 charging on | high = on; pull-down |
| G14 | out | charge current | high = 120 mA, low = 60 mA; pull-down |
| G36 | in (ADC1_CH0) | meter 5 V | V<sub>G36</sub> = V<sub>METER</sub> × 68/168 = 0.405 × V<sub>METER</sub>; use 11 dB attenuation |
| G34 | in (ADC1_CH6 / digital) | existing reader requests | V<sub>G34</sub> = V<sub>REQ</sub> × 68/115; > 1.5 V = requesting |
| G21 / G22 | I²C SDA / SCL | LED dimmer U5 at 0x62 (shared with the CoreInk's RTC at 0x51) | see § 4.7; LEDs at full brightness until set up |
| GND, BAT, 5V_OUT | power | | 3V3 and 5V_IN are not used |

Diagnosis the firmware can show on the e-ink screen:

| VMETER (G36) | Data on G13 | Meaning / message |
|---|---|---|
| 4.5–5.5 V | yes | OK (DSMR ≥ 4) |
| 4.5–5.5 V | no | meter does not send: request not reaching it, or cable in the wrong socket |
| < 0.5 V | yes | DSMR 2/3 meter (no P1 supply) – mains power needed |
| < 0.5 V | no | no meter connected, crossed cable, or the cable is in the wrong socket |
| sagging < 4.6 V | – | P1 supply overloaded: lower the charge current or switch charging off |

## 6. Calculations

* **Pull-up and edges.** R3 = 1 kΩ, line capacitance ≈ 1 nF (1 m cable plus inputs): τ ≈ 1 µs, well below the 8.7 µs bit time.
* **Request level.** V5 = 5.0 V − 0.3 V (BAT54C) = 4.7 V; Q3 drops < 10 mV at 1 mA → 4.7 V ≥ 4.0 V (DSMR). Via D7 only: reader's 5 V − 0.35 V.
* **ADC.** 5.5 V × 0.405 = 2.23 V, within the 11 dB range (≈ 2.45 V) of ADC1.
* **Current budget at the meter (DSMR 5, worst case).** Pull-up 5 mA + LEDs 3 mA + logic < 1 mA + charging 120 mA = 129 mA, leaving ≥ 120 mA for the existing reader. With 60 mA charging: ≥ 180 mA left. The LED dimmer adds < 0.1 mA (U5 idle, U6, R33 while the LEDs are on).
* **Charger dissipation.** (5.0 − 3.6 V) × 0.12 A = 0.17 W in the ESOP-8 TP4056: fine without a heat sink.
* **Simulation.** See [simulation/README.md](simulation/README.md): data path at 115 200 Bd (bit-width error ≤ 0.6 % with a normal meter output; a slow, current-limited output adds edge distortion of ≈ 20 % of a bit, set by the meter itself), request levels in all combinations, charger inrush and the crossed-cable case (1.8 mA from the meter, no node outside its ratings except G34, which sees −2.9 V through 47 kΩ: ≈ 50 µA into its clamp diode).
* **Energy balance.** A CoreInk that measures every 10 minutes and sleeps in between averages far below 60 mA; so 60 mA continuous charging is enough on DSMR 5, and the battery covers the Wi-Fi peaks (up to ~500 mA). *Verify* with a power profiler.

## 7. Mechanics

Measured from the official M5Stack CoreInk model and a photo of the back (coordinates from the top left corner of the back, HAT edge up, in mm):

| Feature | Position |
|---|---|
| Outline | 40 x 56, corner radius ≈ 3 |
| LEGO-compatible holes (Ø 4.85, counterbore Ø 6.2) | (4, 4), (36, 4), (4, 52), (36, 52) |
| MI-BUS socket (2x8, 2.54 mm), centre | (33.97, 36.87); GND bottom right, G23 top right |
| Case screws M2 | (11, 52), (29, 52) |
| Magnets (inside, only in the top half) | ≈ (12, 11) and ≈ (28, 17) – *verify* |
| Recess behind the HAT header | x 9–31, y 0–8.5 |

* **Board:** 40 x 56 mm, the CoreInk outline. The meter socket J2 sits at the top edge (opening up): the device hangs from a short cable under the P1 port with the screen upright. The socket for the existing reader J3 is at the bottom edge (opening down).
* **CoreInk connection** (*being redesigned, see § 9a*): a 2x8 stackable female header (long pins) is inserted from the top and soldered by JLC like any THT part. Its pins pass through the board into the CoreInk socket; the female body on top keeps the MI-BUS available for measurements. Gap board–CoreInk: 3.5 mm, enough for the RJ12 leads and pegs.
* **Shipping by letterbox post:** a PostNL letterbox parcel is at most 38 × 26.5 × 3.2 cm. The modules ship loose,
  side by side, not stacked (CoreInk + P1-BASE stacked is ≈ 34 mm). Each module must stay ≤ 27 mm thick from the
  lid top to the tips of its LEGO posts, which leaves ≥ 5 mm for the box and padding; `enclosure/kuip.py` asserts
  this (P1-BASE: 24.7 mm). The posts are longer than the J1 pins, so a loose module rests on its posts. Cells
  (BatteryBASE) are never shipped in the parcel; the user clicks the modules together.
* **LED windows and lid:** three 2.0 x 1.4 mm windows in the tray's top wall, in front of the side-looking LEDs. The lid
  clicks onto the tray: a thin lip (1.0 mm) with two half-round bumps on each long side snaps into grooves in the long
  walls; a notch in the top of the bottom wall lets a fingernail or a coin lift it off again. No screws.
* **Enclosure (*kuip*)** (*steel discs and nocks replaced by LEGO posts, see § 9a*): see [`enclosure/`](../enclosure). The tray has a rim that holds the CoreInk with cut-outs that only fit the right way round (asymmetric side features). Tapered pegs in the LEGO holes centre it. Three board pegs (H1–H3) key the PCB in the tray. Optional pockets for 8 x 1 mm steel discs sit opposite the two magnets; they hold the CoreInk and only attract in the right orientation.
* The two RJ12 sockets are 14.5 mm tall (LCSC data for C77859): BASE + CoreInk stacked are ≈ 36 mm, so they ship separately in a letterbox parcel and are clicked together at home.

## 8. Production

* Two-layer board, 1.6 mm, JLCPCB standard capabilities (track/space ≥ 0.2 mm, via 0.6/0.3 mm).
* All parts on the top side; SMD plus three THT parts (J1–J3) that JLC solders.
* Basic parts: all resistors and capacitors, AO3401A, 2N7002, 1N5819WS, XC6206P332MR. Extended parts (each adds a one-off loading fee per order): TP4056, 74LVC1G14, 74LVC1G17, BAT54C, SMF6.0A, PESD5V0S1BB, PCA9633DP1, the three side-looking LEDs, RJ12 jacks, stacking header.
* Assembly variants: R6 (pull-up on the splitter output) and R15 (always request) are not fitted by default.
* JLCPCB *Economic* assembly needs a HASL finish (it is not offered with OSP); LeadFree HASL is fine.
* JLCPCB places parts with the LCSC footprints, whose origin or rotation differs for some parts. `tools/export_fab.py` corrects the CPL (`JLC_CORR`: SOT-23, SOT-23-3 and SOT-23-5 +180°, SOIC-8 and TSSOP-8 +270°, RJ12 jack offset to the pin centre and +90°, CoreInk header +90°). Checked in the JLCPCB placement preview in November 2026: pin 1 and orientation of all parts match.
* JLCPCB quote (November 2026, 5 boards, Economic, LeadFree HASL, without shipping and VAT): PCB € 4.71, assembly € 38.97 (setup € 7.46, stencil € 1.40, parts € 8.68, extended-part fees € 14.00, SMT € 1.24, hand soldering € 3.27, manual assembly € 2.09, nitrogen reflow € 0.82); total € 43.68, about € 8.70 per board (with C72555 as J1, before the LED dimmer). Quote of 15 November 2026 for the board with the LED dimmer, same options, **without J1** (the ESQ is a pre-order part, JLCPCB cannot select it yet): PCB € 4.71, assembly € 57.26 (setup € 7.46, stencil € 1.40, parts € 22.38, extended-part fees € 19.59, SMT € 1.42, hand soldering € 3.27, manual assembly € 0.90, nitrogen reflow € 0.82); total € 61.97. The PCA9633DP1 alone costs € 13.92 for five (€ 2.78 each). J1 (ESQ-108-24-G-D) adds about € 18.32 for five plus one extended-part fee and its pre-order handling: roughly € 85 in total, about € 17 per board.
* Prototype order (15 November 2026): the routed board with U4 = 74LVC1G17 quotes at € 65.93 without J1 (PCB € 4.71, assembly € 61.22). Five J1 were pre-ordered through JLCPCB's parts manager, so JLCPCB solders J1 too (no soldering by the user); the PCBA order with J1 follows once the parts are in stock. Fallback if they arrive too late: order without J1 and have J1 fitted by hand. Placement preview checked by hand: the three side-looking LEDs have their lens towards the top edge and their cathode (pad 1) on the left, as in KiCad. Enclosures go in the same shipment: MJF PA12 black, 5 sets, P1-BASE tray + lid $ 19.40 and BatteryBASE tray + lid (fit check) $ 18.70.

## 9. Design decisions

| # | Decision | Alternatives considered | Why |
|---|---|---|---|
| D1 | Stay a CoreInk extension (ESP32, 4 MB, 2.4 GHz) | BASE with its own ESP32-C5/S3; front end usable on a later host | A CoreInk already provides screen, battery, RTC and buttons; the C5/S3 generation is a separate later design |
| D2 | Active splitter in hardware powered by the meter | Passive (symmetric/asymmetric), active via firmware (re-transmit) | Independent of the CoreInk; spec-conform open-drain output; no optocoupler speed problem |
| D3 | Request OR with PMOS + diode fallback, no DIP switches | Keep DIP; firmware only | No user configuration; the reader can always request; full 4.7 V level; works without power |
| D4 | Charge the battery via BAT with a TP4056 | Current-limited load switch to 5V_IN | Exact, constant current from the meter; no back-feeding from USB; the battery buffers peaks |
| D5 | One 74LVC1G14 at V5 for splitter and ESP32 (divider to G13) | Separate 74LVC1G14 at 3.3 V for the ESP32; 74HC14 (v2.7) | Same input thresholds as the lab-tested v2.7 front end; single-gate part is smaller; the splitter path is independent of the CoreInk |
| D6 | RJ12 jacks on the board, cable supplied | Captive cable soldered to the board | No soldering in production; the electronics survive a crossed cable or swapped sockets, and firmware explains |
| D7 | Stacking header from the top | Standard header on the bottom (v2.7) | JLC can assemble it without a second side; the bus stays reachable |
| D8 | Keying by the enclosure rim, not by the header | LEGO pins on adjacent corners; screws | Robust; no loose parts; the header is not designed to take force |
| D9 | ~~Steel-disc pockets optional~~ dropped (§ 9a) | Magnets in the BASE; nothing | The CoreInk's magnets are only in the top half, so steel discs add holding force and a second key; empty by default |
| D10 | One dimmer for all three LEDs (I²C driver switching their supply), powered from the meter side | Per-LED control by firmware (LEDs on the driver's outputs); PWM from an ESP32 pin | Keeps the LEDs showing real hardware states, also without a CoreInk; one setting is enough against disturbing light; the ESP32 has no free pin and is off most of the time |
| D11 | Side-looking LEDs at the top edge | Light holes in the lid; light pipes | The lid is covered by a BatteryBASE in a stack; the device is seen from above |
| D12 | Lid clicks onto the tray | Loose lid; M2 screws | Same click-together principle as the rest of the stack; no tools |

## 9a. Redesign in progress

Decided in November 2026, after the independent checks (§ 12) and the BatteryBASE plans; **the schematic already
has the circuit changes, the PCB and enclosure do not yet** (DRC with schematic parity fails on purpose until the
board is redone):

1. **U4 instead of R4/R32** (finding A): a Schmitt buffer powered from the CoreInk's 3V3 drives G13, with C10 100 nF.
   Nothing flows into a switched-off CoreInk; G13 high is exactly 3.3 V. First a 74LVC1G14 on `P1_DATA`; since
   15 November 2026 a **74LVC1G17 (C7836) fed from `SPLIT_DRV`** (U1's output), see open point 11.
2. **D1 = SMF6.0A** (C178260, finding B): stand-off 6.0 V, above any meter voltage.
3. **Gap CoreInk–PCB from 3.5 to 2.5 mm**: the RJ12 leads are at most 1.9 mm below the board (datasheet), leaving
   0.6 mm clearance. Done in `enclosure/kuip.py`.
4. **No steel-disc pockets** in the tray: the friction of the pins and the tray hold the CoreInk.
5. **Same back as the CoreInk, so one BatteryBASE fits both:** the P1-BASE's lid repeats the CoreInk's back. J1
   becomes a **raised socket** whose top is flush with the lid (≈ 16.5 mm above the board, 8 mm deep) with pins long
   enough to go 6 mm into the CoreInk (≈ 8.5 mm below the board); part: **Samtec ESQ-108-24-G-D**
   (JLCPCB C21241050, pre-order): socket top 13.59 mm above the board ("C"), tail 9.65 mm below the board's top
   ("B"), 8.51 mm deep socket (Samtec ESQ table 1). With the 2.5 mm gap the pins go 5.5 mm into the CoreInk; the lid
   is set flush with the socket top. ESQ-108-49 is the same with low-insertion-force contacts. Lower RJ12 jacks (10–11.5 mm) would make the P1-BASE thinner and the
   raised socket 3–4.5 mm lower.
6. **LEGO posts on every enclosure:** four posts underneath, at the CoreInk's LEGO holes (through holes; a LEGO
   Technic pin fits, measured), 7 mm long so they engage before the 6 mm pins and protect them in transport, with
   three crush ribs for light friction (0.05 mm interference); the post grows out of the corner block, no flared root below it (that would sit in the CoreInk's back). The P1-BASE lid has four matching
   LEGO holes (tubes under the lid) and a cut-out for the raised socket. Done in `enclosure/kuip.py`.
8. **Lower RJ12 jacks: EVERCOM 5301-6P6C** (C3097716, JLCPCB stock): 11.45 mm high instead of 14.5 mm (13.30 x 18.05 mm,
   leads 3.0 mm below the seating plane, snap-in posts Ø3.2 mm, latch down; EVERCOM drawing 5301-660XXX). The footprint
   `p1base:RJ12_EVERCOM_5301-6P6C` is the LCSC footprint, so JLCPCB places it without correction. The P1-BASE gets
   3 mm thinner (lid at ≈ 17.6 mm above the CoreInk) and the raised socket for J1 needs ≈ 13.5 mm instead of 16.5 mm.
7. **RJ12 jacks centred** on the board's long axis (both on the centre line), so the device hangs straight when the
   cables pull. This moves most parts, so the board is placed and routed again.

9. **LEDs visible at the top, dimmable, lid clicks on** (November 2026): § 4.6, § 4.7, § 7; decisions D10–D12.

How to redo the board (on a machine with ≈ 5 GB free memory): `tools/gen_pcb.py` (placement, Freerouting,
stitching, island vias; `P1BASE_VARIANT=<n>` rotates the packing order of block 3 if a GND pad ends up boxed in),
then `tools/pcb_cleanup.py`, then `kicad-cli pcb drc --schematic-parity --refill-zones --save-board`; if DRC reports
an unconnected GND zone, `tools/pcb_bridge_gnd.py` adds a via that ties the boxed-in GND island to the pour, and DRC
runs again; then
`tools/export_fab.py`. The committed board (November 2026, default variant) needed one hand-added route: Freerouting
left PROG (U3 pin 2 to R27) open; it now runs on B.Cu above C8 and down the left edge on F.Cu. The re-route with
U4 = 74LVC1G17 (15 November 2026) needed a different hand fix: a /CHG_IN loop around Q7 boxed in Q7 pin 2 (GND) on
both layers, so `pcb_bridge_gnd.py` found no room; the lower F.Cu leg of that loop (y = 136.5 mm) was moved to B.Cu
with a via at (109.9, 137.3) next to U3 pin 8, which opens the pour to the GND via below Q7. Freerouting does not
give the same result on every run, so a re-route may need a different fix. Then
`enclosure/kuip.py` and `tools/checks/run_checks.py`.

## 10. Open points to verify

1. **Blocking: the CoreInk connector part.** C72555 is listed as "Extended Female Pin Header 3.8"; its LCSC/EasyEDA 3D model has only ≈ 3 mm of pin below the body, so it ends ≈ 1.4 mm under the board, 2.1 mm short of the CoreInk back (confirmed by check 5, § 12). The CoreInk socket is 8 mm deep and flush with the case (measured). A top-mounted stacking header therefore needs a tail of 10–13 mm below its body (1.6 mm board + 3.5 mm gap + 5–8 mm engagement); no part with a known tail length is in the JLCPCB library (November 2026) and C72555 has no datasheet.
   **Decision (November 2026), refined in § 9a: the P1-BASE repeats the CoreInk's back with a raised socket.** First decision: It keeps the bus available on the back, so a NeedForHeat BatteryBASE (separate repository) can be stacked behind the P1-BASE. The exact part (tail ≥ 10.5 mm, e.g. via JLCPCB global sourcing) is still to be selected. The RJ12 datasheet (CONNFLY DS1133-S60BPX) confirms leads of 3.2 ± 0.3 mm below the seating plane, i.e. 1.6–1.9 mm below the board.
   *Considered and rejected:* the LCSC model of the RJ12 jack puts its leads 3.2 mm below the **seating plane** (PCB top), i.e. only ≈ 1.6 mm below the board, and the posts ≈ 1.3 mm. If the datasheet or a sample confirms this, a plain 2x8 male header on the bottom (as in v2.7, 2.5 mm plastic) leaves ≈ 0.9 mm under the jack leads; the tray's disc pads (1.6 mm) would then have to move clear of the jacks, and JLCPCB would have to solder a THT part on the bottom side.
2. RJ12 jack C77859 (CONNFLY DS1133-S60BPX): its LCSC footprint matches the Wayconn MJEA-660X1 footprint (same pin and post positions after a 90° rotation, pin 1 at the same place); the body is 14.5 mm tall and 14.6 mm wide (Wayconn outline: 12.2 mm), which clears the neighbouring pads. In the JLCPCB 3D preview the jack front reaches about 1 mm past the board edge; check against the datasheet (fine for the cable, but the enclosure opening must allow it).
3. TP4056 behaviour in parallel with the CoreInk's own charger on USB. From the CoreInk schematic (M5Stack, `coreink_sch.pdf`): the bus pin `BAT` is net `SYS_BAT`, wired straight to battery connector J4 and to the `BAT` pin of the CoreInk's TP4057 (U6); there is no protection IC on the CoreInk board (the cell pack's own protection is assumed). The TP4057 is set to ≈ 200 mA (R45 = 5.1 kΩ) and is fed from net `CHG` = USB 5 V (through D8) or the bus pin `5V_IN`, behind a 1 A PTC. So both chargers do drive the same cell node; both stop at 4.2 V. With USB and P1 charging at 120 mA the cell can get ≈ 320 mA (≈ 0.8 C for 390 mAh): keep 60 mA as the default. To measure: charge termination with both chargers active.
4. ~~CoreInk `5V_OUT`~~ answered by the schematic: `5V_OUT` (net `EXT_5VO`) comes from the SY7088 boost converter (U5) through D11; the boost is enabled by the power switch (`PS_EN`), so `5V_OUT` is present whenever the CoreInk is on (battery or USB) and absent when it is off. The bus `3V3` is the SY8089 buck output (`MCU_VDD`), fed from the boost output, so it is also off when the CoreInk is off: U4 is then unpowered, as intended. The schematic also confirms the choice not to feed `5V_IN`: `5V_IN` (net `EXT_5VI`) feeds the TP4057 and, through D9, the boost converter (so the meter would carry the whole system load), and USB 5 V reaches `5V_IN` through D8 (so USB power would flow out to the meter).
5. Positions of the magnets (± 2 mm).
6. Reading Landis+Gyr E350/E360 and DSMR 2/3 meters with the v3 front end.
7. Existing readers on J3: HomeWizard P1 meter, IUNGO, others; with and without their own request.
8. Side-looking LEDs (LTST-S220): the Lite-On drawing could not be downloaded; the footprint covers the pad centres of
   all three LCSC footprints. Check in the JLCPCB placement preview that the lens faces the board edge (CPL rotation),
   and on the first board the lens height (the tray windows assume 0.5 mm above the board, 1.4 mm tall).
9. I²C pull-ups on G21/G22 inside the CoreInk (they serve the RTC); the P1-BASE adds none.
10. Snap fit of the lid (bump 0.35 mm, groove 0.55 mm deep): print a test and adjust `SNAP_P` in `enclosure/kuip.py`.
11. **G13 with a slow meter output (simulation, 15 November 2026).** U4 (74LVC1G14 at the CoreInk's 3.3 V) takes its
    input from `P1_DATA`, like U1. At 3.3 V its thresholds are lower (≈ 1.8 V / 1.1 V instead of ≈ 2.75 V / 1.65 V at
    5 V), so with a slow, current-limited meter output (opto, 4 mA) the slow falling edge crosses late: the bit-width
    error on G13 is ≈ 46 % instead of ≈ 21 % (docs/simulation § 1), close to what a UART can take. Fast meter outputs
    are fine (0.4 %). **Done (schematic, 15 November 2026):** U4 = 74LVC1G17 (C7836, non-inverting Schmitt buffer,
    same pinout, 5 V tolerant input) fed from `SPLIT_DRV` (U1's clean 5 V output): same polarity at G13, U1's
    thresholds, still nothing into a switched-off CoreInk. One more extended part (≈ € 2.80 per order). Simulated: bit-width
    error on G13 with the slow meter output back to ≈ 21 % (same as the splitter output), fast outputs 0.6 %.

## 11. Out of scope

* DSMR 6 / X1 (from 2027): Ethernet (RJ45) with a REST/WebSocket API and USB-C power; this BASE does not apply.
* Measuring the current drawn by the existing reader (only the meter voltage is monitored).
* Galvanic isolation: the P1 port is isolated inside the meter.

## 12. Independent checks

Besides ERC/DRC in KiCad, `tools/checks/run_checks.py` runs four checks that use other data or other software than the
tools that made the design. Reports: [`docs/checks/`](checks/). Results of November 2026:

| # | Check | How | Result |
|---|---|---|---|
| 1 | Footprints and pinout against JLCPCB's library | Fetch the LCSC symbol and footprint of every BOM part (easyeda2kicad), place them as JLCPCB does from our CPL, and test that each LCSC pad lands on exactly one, distinct pad of ours; list LCSC pin function → our pin and net | All 161 pads land correctly; every pin function (G/S/D, A/K, TP4056, 74LVC1G14) matches |
| 2 | Worst-case voltage per pin | Hand-derived worst-case voltage of every net (meter 5.5 V) against the absolute maximum rating of every connected pin; a pin without a limit is reported | See findings A and B |
| 4 | Gerbers against the schematic | Rebuild the copper from the gerber and drill files alone (gerbonara + shapely; the net attributes in the files are ignored), find the connected islands and compare them with the netlist exported from the schematic | 47 nets, no opens, no shorts (a removed trace and an added short in a test copy were both caught) |
| 5 | 3D fit | CadQuery/OpenCascade: populated board (KiCad STEP), tray and lid, a CoreInk proxy with the 8 mm socket, and RJ12 plugs with cable; pairwise overlap volumes and closest approach | After fix C: no collisions; plugs pass the openings; lowest part under the board 2.1 mm above the CoreInk |

Check 3 (SPICE with tolerances) is still to be added to `tools/sim/`.

Findings:

* **A. G13 back-feeds a switched-off CoreInk.** The 4k7/10k divider from the 5 V splitter output drives G13 to 3.2 V
  (3.57 V at a 5.5 V meter, close to the ESP32's 3.6 V maximum). When the CoreInk is off but the meter powers the
  P1-BASE, G13 idles high and pushes ≈ 1 mA through the ESP32's protection diode into its unpowered 3.3 V rail. This can
  partly power the ESP32 and disturb its power-on reset. Proposed fix: replace the divider with a single-gate buffer powered
  from the CoreInk's 3V3 pin (e.g. 74LVC1G17, whose input tolerates 5.5 V and which is high-impedance when unpowered).
  G36 (43 µA, continuous) and G34 (0.1 mA, only while a reader requests) are minor.
* **B. TVS stand-off voltage.** SMF5.0A and PESD5V0S1BB have a 5.0 V stand-off voltage; a meter at the top of its tolerance
  (5.5 V) or the reader's own 5 V puts them above it, where leakage rises. Consider 6 V stand-off parts (e.g. SMF6.0A).
* **C. Lid against the jacks (fixed).** The lid's centring lip and the tongues over the RJ12 openings reached 0.3–0.9 mm into the
  top of the jacks. The lip now has a notch above each jack and the tongues stop 0.2 mm above them (`enclosure/kuip.py`).
* **D. Stacking header (known, § 10 point 1).** Confirmed numerically; see the reopened bottom-header option there.

## 13. Schematic drawing conventions

The schematic is generated by `tools/gen_schematic.py` from a circuit description (every part with the net on each pin);
after writing it, the script exports the netlist with kicad-cli and stops if it differs from that description. The
drawing follows conventions taken from the NeedForHeat and Twomes hardware repositories (P1 Gateway, BoilerBASE,
OpenTherm Monitor, P1-BASE v2.7):

* one sheet (A3), one dashed frame per function block with a numbered title; signal flow from left to right;
* wires inside a block; net labels only where a signal goes to another block or connector;
* power symbols for the rails (`VMETER`, `V5`, `GND`): supplies point up, ground points down;
* every net has a name (small labels on internal nets), so board, firmware notes and this document use the same names;
* references and values horizontal and next to their part; `DNP` parts crossed out;
* short notes on the sheet for anything that is not obvious, the firmware interface next to the CoreInk connector,
  a revision history, and a complete title block (licence, origin, revision, date).

`tools/sync_pcb_nets.py` copies changed net names to the board without touching the copper (nets are matched by
their pads); DRC with schematic parity then confirms that schematic and board agree.

