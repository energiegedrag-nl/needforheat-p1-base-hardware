# P1-BASE v3 enclosure (*kuip*)

Two printed parts:

| File | Part |
|---|---|
| `fabrication/p1-base-kuip.step` / `.stl` | tray: holds the PCB on four corner posts and centres the CoreInk |
| `fabrication/p1-base-lid.step` / `.stl` | lid with light holes above the three LEDs and tongues that close the RJ12 openings |

`kuip.py` is the parametric source (CadQuery 2.x): `python enclosure/kuip.py`. It reads the LED and jack positions from `pcb_features.json`, which `tools/gen_pcb.py` writes. `p1-base-v3-pcb.step` is the populated board, for checking the fit in a CAD program.

How it works (frame: back of the CoreInk, HAT edge up):

* The CoreInk's back rests on four corner posts; tapered **nocks** under the posts go into its four LEGO-compatible holes and centre it.
* The PCB rests on the same posts, 3.5 mm above the CoreInk, and is keyed by **three pegs** (the fourth corner has none).
* A short **skirt** continues the wall 3 mm down over the CoreInk's sides, with openings for the HAT connector, USB-C, the Grove port, the dial and the power switch.
* Two pads with **pockets for 8 x 1 mm steel discs** sit opposite the CoreInk's built-in magnets (top half only). They are optional: the header and the skirt already hold the CoreInk; the discs add holding force and only line up with the magnets in the right orientation.
* A triangle on top of the meter-side wall points to the meter socket.

Values to verify on the first print (see `kuip.py`): RJ12 jack height (`JACK_H`), magnet positions (`MAGNETS`), the length of the stacking-header pins against `GAP`, and the skirt openings against a real CoreInk.

Print: PETG, 0.2 mm layers. Kuip with its top rim on the bed (nocks pointing up) and supports under the corner posts; lid with its flat side on the bed. A printing service (SLA resin or MJF nylon) needs no special orientation.
