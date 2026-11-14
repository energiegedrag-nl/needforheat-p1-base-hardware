# TODO – needforheat-p1-base-hardware

Open work for this repository, distilled from the earlier NeedForHeat backlog at Windesheim, including the discussions on it (paraphrased and regrouped), and from the 2026 maintenance review.

Items that touch several repositories are written out in full in one *lead* repository; the others list them with a link (→). Keep the details up to date in the lead repository only.

## Soon: robustness and correctness

- [ ] <a id="v3proto"></a>**Build and test a P1-BASE v3.0 prototype.** Order a few assembled boards and print the enclosure; check the points listed in [docs/design-v3.md](docs/design-v3.md#10-open-points-to-verify): stacking-header fit, RJ12 jack height and pinout, TP4056 in parallel with the CoreInk charger, CoreInk `5V_OUT` behaviour, magnet positions, and reading DSMR 2–5 meters (including Landis+Gyr E350/E360) with common P1 readers on the second socket. Also affects: needforheat-p1-reader-firmware.
- [ ] → Landis+Gyr meters — see [needforheat-p1-reader-firmware](https://github.com/energiegedrag-nl/needforheat-p1-reader-firmware/blob/main/TODO.md#lg)

## Later: features and ideas

- [ ] <a id="isense"></a>**Measure the current of the existing reader.** v3 only measures the meter voltage; a current sense on J3 pin 1 would let firmware budget the P1 supply exactly.
- [ ] → Modular enclosures and a battery base — see [needforheat-boiler-monitor-hardware](https://github.com/energiegedrag-nl/needforheat-boiler-monitor-hardware/blob/main/TODO.md#modular)

## Recently done

- [x] <a id="splitter"></a>**P1-BASE splitter architecture.** Chosen for v3.0: an active splitter in hardware, powered by the meter, with an open-drain output; the trade-offs are in [docs/design-v3.md](docs/design-v3.md#9-design-decisions).
- [x] v3.0 design: data request without DIP switches, charging from DSMR 5 meters, protection against crossed cables, LEDs, enclosure.
