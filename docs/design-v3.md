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
- [5. Firmware interface](#5-firmware-interface)
- [6. Calculations](#6-calculations)
- [7. Mechanics](#7-mechanics)
- [8. Production](#8-production)
- [9. Design decisions](#9-design-decisions)
- [10. Open points to verify](#10-open-points-to-verify)
- [11. Out of scope](#11-out-of-scope)

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
| Monitoring | none | ADC on meter 5 V (G36), digital/ADC read-back of the external request (G34), three LEDs, test points |
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

| LED | Colour | On when | Current |
|---|---|---|---|
| LED1 | green | data bits on the P1 line | ≈ 1 mA while blinking |
| LED2 | yellow | data request active | ≈ 0.8 mA |
| LED3 | red | battery being charged from the P1 port | ≈ 1.3 mA |

Test points: TP1 `VMETER`, TP2 `V5`, TP3 `P1_DATA`, TP4 `METER_REQ`, TP5 `EXT_DATA_OUT` (splitter output), TP6 `CHG_IN`, TP7 GND.

## 5. Firmware interface

| CoreInk pin | Direction | Function | Notes |
|---|---|---|---|
| G13 | in | P1 data (UART RX) | not inverted; 115 200 8N1 (DSMR ≥ 4) or 9600 7E1 (DSMR 2/3) |
| G26 | out | data request | high = request; pull-down on the BASE |
| G25 | out | P1 charging on | high = on; pull-down |
| G14 | out | charge current | high = 120 mA, low = 60 mA; pull-down |
| G36 | in (ADC1_CH0) | meter 5 V | V<sub>G36</sub> = V<sub>METER</sub> × 68/168 = 0.405 × V<sub>METER</sub>; use 11 dB attenuation |
| G34 | in (ADC1_CH6 / digital) | existing reader requests | V<sub>G34</sub> = V<sub>REQ</sub> × 68/115; > 1.5 V = requesting |
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
* **Current budget at the meter (DSMR 5, worst case).** Pull-up 5 mA + LEDs 3 mA + logic < 1 mA + charging 120 mA = 129 mA, leaving ≥ 120 mA for the existing reader. With 60 mA charging: ≥ 180 mA left.
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
* **CoreInk connection:** a 2x8 stackable female header (long pins) is inserted from the top and soldered by JLC like any THT part. Its pins pass through the board into the CoreInk socket; the female body on top keeps the MI-BUS available for measurements. Gap board–CoreInk: 3.5 mm, enough for the RJ12 leads and pegs.
* **Enclosure (*kuip*):** see [`enclosure/`](../enclosure). The tray has a rim that holds the CoreInk with cut-outs that only fit the right way round (asymmetric side features). Tapered pegs in the LEGO holes centre it. Three board pegs (H1–H3) key the PCB in the tray. Optional pockets for 8 x 1 mm steel discs sit opposite the two magnets; they hold the CoreInk and only attract in the right orientation.
* The two RJ12 sockets are about 11.5 mm tall *(verify)*: BASE + CoreInk stacked are ≈ 33 mm, so they ship separately in a letterbox parcel and are clicked together at home.

## 8. Production

* Two-layer board, 1.6 mm, JLCPCB standard capabilities (track/space ≥ 0.2 mm, via 0.6/0.3 mm).
* All parts on the top side; SMD plus three THT parts (J1–J3) that JLC solders.
* Basic parts: all resistors and capacitors, AO3401A, 2N7002, 1N5819WS, red LED. Extended parts (each adds a one-off loading fee per order): TP4056, 74LVC1G14, BAT54C, SMF5.0A, PESD5V0S1BB, green and yellow LED, RJ12 jacks, stacking header.
* Assembly variants: R6 (pull-up on the splitter output) and R15 (always request) are not fitted by default.

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
| D9 | Steel-disc pockets optional | Magnets in the BASE; nothing | The CoreInk's magnets are only in the top half, so steel discs add holding force and a second key; empty by default |

## 10. Open points to verify

1. Stacking header C72555: pin length below the body (assumed ≥ 10.5 mm) and fit in the CoreInk socket. Its LCSC stock is low (≈ 400 in November 2026); find a second source before a larger order.
2. Height of the RJ12 jack C77859 (CONNFLY DS1133-S60BPX) and whether its pinout matches the Wayconn MJEA-660X1 footprint used since v2.7.
3. TP4056 behaviour in parallel with the CoreInk's own charger (TP4057) on USB.
4. CoreInk `5V_OUT`: is it present on battery power (boost converter on) and when the CoreInk is switched off?
5. Positions of the magnets (± 2 mm).
6. Reading Landis+Gyr E350/E360 and DSMR 2/3 meters with the v3 front end.
7. Existing readers on J3: HomeWizard P1 meter, IUNGO, others; with and without their own request.

## 11. Out of scope

* DSMR 6 / X1 (from 2027): Ethernet (RJ45) with a REST/WebSocket API and USB-C power; this BASE does not apply.
* Measuring the current drawn by the existing reader (only the meter voltage is monitored).
* Galvanic isolation: the P1 port is isolated inside the meter.
