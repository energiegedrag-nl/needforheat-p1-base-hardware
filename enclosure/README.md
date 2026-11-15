# P1-BASE v3 enclosure (*kuip*)

Two printed parts:

| File | Part |
|---|---|
| `fabrication/p1-base-kuip.step` / `.stl` | tray: holds the PCB on four corner blocks, LEGO posts underneath; a light window for each LED, next to its RJ12 opening |
| `fabrication/p1-base-lid.step` / `.stl` | lid that clicks onto the tray: the module's back, with tongues that close the RJ12 openings and corner pillars with LEGO Technic holes |

`kuip.py` is the parametric source (CadQuery 2.x): `python enclosure/kuip.py`. It reads the LED and jack positions from `pcb_features.json`, which `tools/gen_pcb.py` writes. `p1-base-v3-pcb.step` is the populated board, for checking the fit in a CAD program. `callouts.py` renders the parts with numbered callouts (`docs/images/enclosure-*-callouts.png`).

| Tray, top edge | Tray, underside | Lid, inside |
|---|---|---|
| ![](../docs/images/enclosure-tray-top-edge-callouts.png) | ![](../docs/images/enclosure-tray-underside-callouts.png) | ![](../docs/images/enclosure-lid-underside-callouts.png) |

How it works (frame: back of the CoreInk, HAT edge up):

* **The outside is exactly the CoreInk outline** (40 × 56 mm, corner radius 3) and there is no skirt: every module's back equals the CoreInk's back, so any BASE that fits a bare CoreInk also fits behind a P1-BASE. The walls (1.6 mm) are inside that outline; the PCB is 36.3 × 52.3 mm.
* The module stands on four corner blocks on the CoreInk's back; four **LEGO posts** (7 mm, with crush ribs) go into the CoreInk's four LEGO-compatible holes. They are longer than the 6 mm bus pins, so they guide the module before the pins engage and protect the pins in transport. The posts and the 16 bus contacts hold the module; a cable hanging from an RJ12 jack pulls across the posts rather than along them.
* The **lid repeats the CoreInk's back**: four LEGO holes at the same positions and a cut-out for the raised bus socket. Each hole is a **LEGO Technic hole** in a corner pillar of the lid: a counterbore at the entry and a snap groove one Technic module (7.8 mm) deep, so a real Technic pin clicks in as on the CoreInk (LEGO standard values, verify on a print). The tray's walls are notched at the corners for these pillars.
* The PCB rests on the corner blocks, 2.5 mm above the CoreInk, and is keyed by **three pegs**; the top-left corner has none, so the PCB fits one way only.
* An arrow on the lid's outside points to the meter edge.
* Two green **side-looking LEDs**, one beside each RJ12 socket, shine through a window in the wall next to the plug: LED1 in the top (meter-side) wall left of J2, LED2 in the bottom wall right of J3 (seen from the back). They stay visible with a module behind the P1-BASE.
* The **lid clicks on**: a 1 mm lip inside the walls with two half-round bumps on each long side snaps into grooves in the long walls. To open it, lift it at the notch in the bottom wall (left of the J3 opening, seen from the back).

Values to verify on the first print (see `kuip.py`): RJ12 jack height (`JACK_H`), the snap fit (`SNAP_P`, `GROOVE_D`), the LED lens height (`LED_LENS_Z`), the length of the stacking-header pins against `GAP`, and the Technic hole (`TECH_*`) with a real LEGO Technic pin.

Print: MJF PA12 (as ordered for the prototype) or SLA resin need no special orientation. On an FDM printer: PETG, 0.2 mm layers; tray with its top rim on the bed (LEGO posts pointing up) and supports under the corner blocks; lid with its flat side on the bed.
