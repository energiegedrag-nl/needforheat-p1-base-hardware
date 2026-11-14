# P1-BASE v3 enclosure (*kuip*)

Two printed parts:

| File | Part |
|---|---|
| `fabrication/p1-base-kuip.step` / `.stl` | tray: holds the PCB on four corner posts and centres the CoreInk |
| `fabrication/p1-base-lid.step` / `.stl` | lid with light holes above the three LEDs and tongues that close the RJ12 openings |

`kuip.py` is the parametric source (CadQuery 2.x): `python enclosure/kuip.py`. It reads the LED and jack positions from `pcb_features.json`, which `tools/gen_pcb.py` writes. `p1-base-v3-pcb.step` is the populated board, for checking the fit in a CAD program.

How it works (frame: back of the CoreInk, HAT edge up):

* The CoreInk's back rests on four corner blocks; four **LEGO posts** (7 mm, with crush ribs) go into its four LEGO-compatible through holes. They are longer than the 6 mm bus pins, so they guide the module before the pins engage and protect the pins in transport.
* The **lid repeats the CoreInk's back**: four LEGO-compatible holes at the same positions and a cut-out for the raised bus socket, so a BatteryBASE fits behind the P1-BASE as it would on a CoreInk.
* The PCB rests on the same posts, 2.5 mm above the CoreInk, and is keyed by **three pegs** (the fourth corner has none).
* A short **skirt** continues the wall 3 mm down over the CoreInk's sides, with openings for the HAT connector, USB-C, the Grove port, the dial and the power switch.
* A triangle on top of the meter-side wall points to the meter socket.

Values to verify on the first print (see `kuip.py`): RJ12 jack height (`JACK_H`), the length of the stacking-header pins against `GAP`, and the skirt openings against a real CoreInk.

Print: PETG, 0.2 mm layers. Kuip with its top rim on the bed (LEGO posts pointing up) and supports under the corner blocks; lid with its flat side on the bed. A printing service (SLA resin or MJF nylon) needs no special orientation.
