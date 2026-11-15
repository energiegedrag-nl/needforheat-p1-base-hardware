# TODO – needforheat-p1-base-hardware

Open work for this repository, distilled from the earlier NeedForHeat backlog at Windesheim, including the discussions on it (paraphrased and regrouped), and from the 2026 maintenance review.

Items that touch several repositories are written out in full in one *lead* repository; the others list them with a link (→). Keep the details up to date in the lead repository only.

## Soon: robustness and correctness

- [ ] <a id="v3proto"></a>**Build and test a P1-BASE v3.0 prototype.** Order a few assembled boards and print the enclosure; check the points listed in [docs/design-v3.md](docs/design-v3.md#10-open-points-to-verify): stacking-header fit, RJ12 jack height and pinout, TP4056 in parallel with the CoreInk charger, CoreInk `5V_OUT` behaviour, magnet positions, and reading DSMR 2–5 meters (including Landis+Gyr E350/E360) with common P1 readers on the second socket. Also affects: needforheat-p1-reader-firmware.
- [ ] <a id="stackback"></a>**Every module's back must equal the CoreInk's back.** Goal: whatever BASE sat on a bare CoreInk (an M5Stack CoreInk BASE such as the Proto Base, 56 × 40 mm, or our BatteryBASE) still fits behind a P1-BASE. Today the lid repeats the CoreInk's LEGO holes and the flush bus socket, but the tray's outline is 43.7 × 59.7 mm (wall and clearance outside the 40 × 56 mm board) and its skirt wraps 3 mm over the CoreInk's sides; a module with its own skirt cannot fit over that larger outline. Options: (a) outline exactly 40 × 56 mm with the walls inside it (PCB ≈ 36.5 × 52.5 mm, so placement and routing again), no skirt; (b) keep the 40 × 56 mm PCB and accept a larger back that only our own modules match; (c) no walls on the sides at all. Without a skirt the module is held only by the 16 bus contacts and the crush ribs of the four LEGO posts: measure the pull-off force on the prototype, including a pull on the RJ12 cables. Decide before the PCB order is paid (≈ 8 December 2026), because (a) changes the PCB outline. Also affects: needforheat-battery-base-hardware.
- [ ] <a id="hat"></a>**HAT units on the CoreInk's top edge.** M5Stack sells dozens of HATs for the StickC series (sensors, proto board, servo, speaker, battery); several are listed for the CoreInk too, e.g. the 18650C battery HAT. A HAT is about 24 mm wide and 8–24 mm deep and plugs into the 2.54 mm 8-pin header on the CoreInk's top edge; the P1-BASE puts its J2 socket, the meter cable and the three LED windows on the same edge, and the tray's skirt has a 24 mm cut-out there. Check with one or two real HATs (e.g. ENV III, Proto) whether the HAT's body reaches behind the CoreInk's back plane and collides with the tray, the J2 plug or the LED windows; if so, move the cut-out or the LEDs.
- [ ] <a id="arrow"></a>**Orientation arrow on the tray is missing.** `kuip.py` cuts the arrow into the top wall at x = 20 mm, exactly where the J2 opening removes the wall, so the printed tray has no arrow. Move it (e.g. onto the lid, pointing to the meter edge).
- [ ] → Landis+Gyr meters — see [needforheat-p1-reader-firmware](https://github.com/energiegedrag-nl/needforheat-p1-reader-firmware/blob/main/TODO.md#lg)

## Later: features and ideas

- [ ] <a id="isense"></a>**Measure the current of the existing reader.** v3 only measures the meter voltage; a current sense on J3 pin 1 would let firmware budget the P1 supply exactly.
- [ ] → Modular enclosures and a battery base — see [needforheat-boiler-monitor-hardware](https://github.com/energiegedrag-nl/needforheat-boiler-monitor-hardware/blob/main/TODO.md#modular)

## Recently done

- [x] <a id="splitter"></a>**P1-BASE splitter architecture.** Chosen for v3.0: an active splitter in hardware, powered by the meter, with an open-drain output; the trade-offs are in [docs/design-v3.md](docs/design-v3.md#9-design-decisions).
- [x] v3.0 design: data request without DIP switches, charging from DSMR 5 meters, protection against crossed cables, LEDs, enclosure.
