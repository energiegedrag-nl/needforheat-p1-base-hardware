# TODO – needforheat-p1-base-hardware

Open work for this repository, distilled from the earlier NeedForHeat backlog at Windesheim, including the discussions on it (paraphrased and regrouped), and from the 2026 maintenance review.

Items that touch several repositories are written out in full in one *lead* repository; the others list them with a link (→). Keep the details up to date in the lead repository only.

## Soon: robustness and correctness

- [ ] <a id="v3proto"></a>**Build and test a P1-BASE v3.0 prototype.** Assembled boards and printed enclosures are prepared in the JLCPCB cart; the order waits for the stacking header J1 (Samtec ESQ-108-24-G-D, C21241050, pre-ordered), which then has to be added to the PCBA. Check the points listed in [docs/design-v3.md](docs/design-v3.md#10-open-points-to-verify): stacking-header fit, RJ12 jack height and pinout, TP4056 in parallel with the CoreInk charger, CoreInk `5V_OUT` behaviour, and reading DSMR 2–5 meters (including Landis+Gyr E350/E360) with common P1 readers on the second socket. On the printed enclosure: the snap fit of the lid, the lid key (it must stop a turned lid at first touch), and the pull-off force of the module without a skirt (16 bus contacts plus the crush ribs of the LEGO posts), including a pull on the RJ12 cables. Also affects: needforheat-p1-reader-firmware.
- [ ] <a id="batteryflush"></a>**BatteryBASE enclosure flush with the CoreInk outline.** The P1-BASE back now equals the CoreInk's back (40 × 56 mm, no skirt), so any CoreInk BASE stacks behind it; the BatteryBASE enclosure still has the old outline and must follow. Its prints in the JLCPCB cart are the old design. Lead: needforheat-battery-base-hardware.
- [ ] <a id="hat"></a>**HAT units on the CoreInk's top edge.** M5Stack sells dozens of HATs for the StickC series (sensors, proto board, servo, speaker, battery); several are listed for the CoreInk too, e.g. the 18650C battery HAT. A HAT is about 24 mm wide and 8–24 mm deep and plugs into the 2.54 mm 8-pin header on the CoreInk's top edge; the P1-BASE puts its J2 socket, the meter cable and LED1's window on the same edge, and the tray's top wall is open there for the J2 plug. Check with one or two real HATs (e.g. ENV III, Proto) whether the HAT's body reaches behind the CoreInk's back plane and collides with the tray, the J2 plug or the LED window; if so, move the cut-out or LED1.
- [ ] → Landis+Gyr meters — see [needforheat-p1-reader-firmware](https://github.com/energiegedrag-nl/needforheat-p1-reader-firmware/blob/main/TODO.md#lg)

## Later: features and ideas

- [ ] <a id="isense"></a>**Measure the current of the existing reader.** v3 only measures the meter voltage; a current sense on J3 pin 1 would let firmware budget the P1 supply exactly.
- [ ] → Modular enclosures and a battery base — see [needforheat-boiler-monitor-hardware](https://github.com/energiegedrag-nl/needforheat-boiler-monitor-hardware/blob/main/TODO.md#modular)
