# NeedForHeat P1-BASE hardware <!-- omit in toc -->

This repository contains the open hardware design files for the NeedForHeat P1-BASE device, which can be used as a [CoreInk BASE extension module](https://docs.m5stack.com/en/coreink/proto_base), on the back of an [M5Stack CoreInk](https://docs.m5stack.com/en/core/coreink) device. 

> **Own deployment.** This repository is maintained by [energiegedrag-nl](https://github.com/energiegedrag-nl) and deployed under `energiegedrag.nl`. To run your own instance, replace `energiegedrag-nl` by your GitHub organisation and `energiegedrag.nl` by your domain (hosts used: `api.<domain>`, `manuals.<domain>`), consistently in configuration and build settings.

The NeedForHeat P1-BASE enables reading [smart meters that adhere to the Dutch Smart Meter Requirements](https://github.com/energiegedrag-nl/dsmr-info) via the [P1 port](https://nl.wikipedia.org/wiki/P1-poort).

<img src="./images/pcb.jpg" width="600"  />

## Table of contents <!-- omit in toc -->
- [General info](#general-info)
- [Producing](#producing)
  - [Printed Circuit Board](#printed-circuit-board)
  - [Enclosure](#enclosure)
- [Deploying](#deploying)
  - [Cost](#cost)
  - [Connecting](#connecting)
  - [Setting the DIP Switches](#setting-the-dip-switches)
- [Developing](#developing)
  - [Printed Circuit Board](#printed-circuit-board-1)
- [Features](#features)
- [Status](#status)
- [License](#license)
- [Citation](#citation)
- [Credits](#credits)

## General info
This repository contains the open hardware designs files for the NeedForHeat P1-BASE. It also includes a `docs` folder with recent printouts of the [schematics](./docs/needforheat-p1-base-hardware-sch.pdf) and [PCB layout](./docs/needforheat-p1-base-hardware-pcb.pdf). 

For the associated firmware that you can run on this device, please see [this repository](https://github.com/energiegedrag-nl/needforheat-p1-reader-firmware).

## Producing

### Printed Circuit Board
To manufacture the printed circuit board you can use various PCB services. 

The folder [pcb/jlcpcb](./pcb/jlcpcb) includes all exported files needed to have the PCBs manufactured by [JLCPCB](https://www.jlcpcb.com). Upload the [zipped gerber files](./pcb/jlcpcb/assembly/GERBER-needforheat-p1-base-hardware.zip) to the [JLCPCB quote page](https://cart.jlcpcb.com/quote), select the amount of PCBs and a colour for the silkscreen. All other options can be left on default. 

If you do not want to solder components on the PCB yourself, select `PCB assembly` and JLCPCB will do it for you (even for through-hole components if you so desire). This will take you to a page where the BOM and POS file can be uploaded. Use the files [BOM-needforheat-p1-base-hardware.csv](./pcb/jlcpcb/assembly/BOM-needforheat-p1-base-hardware.csv) and [CPL-needforheat-p1-base-hardware.csv](./pcb/jlcpcb/assembly/CPL-needforheat-p1-base-hardware.csv).

JLCPCB provides detailed steps on their website to select component assembly, including wave soldering. For wave soldering or through-hole component assembly, specify this requirement when uploading your BOM and POS files. 

> After uploading BOM and CPL, you may be asked to select a component for `Q3`. You do not need to do so and can select 'do not place'. For more information, see the [design document](docs/documentation.md#optional-components).





### Enclosure

An enclosure for this device has not been developed yet.

<!-- an enclosure has not been developed yet
To fabricate the enclosure you can use your own 3D printer or use a 3D printing service. 

<img src="./images/enclosure.jpg" height="600" />

The folder [enclosure/fabrication](./enclosure/fabrication) contains exported STL files for the [case](./enclosure/fabrication/twomes-hardware-repository-template-case.stl) and [lid](./enclosure/twomes-hardware-repository-template-lid.step) of the NeedForHeat P1-BASE enclosure. The STL files can be imported into any slicer and turned into G-Code for a 3D printer.
-->

## Deploying

To deploy P1-BASE to a home as the NeedForHeat Smart Meter module, in addition to the PCB you need additional hardware: enclusure, M5Stack CoreInk, a short RJ12 cable and for some homes a power adapter. In this section we describe the cose and connections.

### Cost

Prices indicate price per module in June 2024, based on ordering enough hardware for 10 modules, including 21% VAT and shipping to an address in the Netherlands.

| #   | Item                                                                                                                                                 | Supplier    | Price per Unit |   Subtotal |  Shipping |      Total |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | -------------: | ---------: | --------: | ---------: |
| 1   | P1-BASE PCB                                                                                                                                          | JLCPCB      |          €2.40 |      €2.40 |     €2.38 |      €4.78 |
| 1   | P1-BASE enclosure                                                                                                                                    | JLCPCB      |          €1,30 |      €1,30 |     €2,40 |      €3,60 |
| 1   | [M5Stack CoreInk](https://www.tinytronics.nl/nl/platformen-en-systemen/m5stack/e-paper/m5stack-m5core-ink-met-1.54-inch-e-paper-e-ink-display-esp32) | TinyTronics |         €43.00 |     €43.00 |     €0.00 |     €43.00 |
| 4   | [LEGO pen stroef + pen stroef](https://www.blokjeskoning.nl/product/pen-stroef-pen-stroef-zwart/) | Blokjeskoning |         €0.03 |   €0.12 |    €0.30 | €0.42 |
| 1   | [RJ12 cable (male-male; 6P6C; straight; 0.5 m or shorter)](https://www.amazon.nl/-/en/InLine-18848A-Modular-Cable-6-Core/dp/B005I1UDOE/)[^1]         | AlleKabels  |          €5.95 |      €5.95 |     €0.00 |      €5.95 |
| 1   | [USB-A 230V charger + USB-A to USB-C cable](https://www.allekabels.nl/usb-oplader/4508/3636716/usb-a-oplader-usb-c-kabel.html)                       | AlleKabels  |         €14.95 |     €14.95 |     €0.13 |     €15.08 |
|     | **TOTAL**                                                                                                                                            |             |     **€67.60** | **€67.72** | **€6,21** | **€72,83** |

[^1]: The shorter the cable the better: this allows users to simply click in the RJ12 connector of te to the P1 port of their smart to leave and leave the NeedForHeat smart meter reader device dangling from the P1-port;*

### Connecting

Assuming that the PCB is fully assembled, the device has an enclosure, and the device has been programmed with the [needforheat-p1-reader-firmware](https://github.com/energiegedrag-nl/needforheat-p1-reader-firmware), you can proceed and connect the device as follows:

Before sending the device to a home:

1. Mount the P1-BASE in its enclosure.
1. Connect the short RJ12 cable to the upper female RJ12 connector[^2].
1. Insert 2 lego pens in the enclusure at opposite diagonal corners. 
1. Insert 2 lego pens in the holes on the back side of the M5Stack CoreInk at opposite diagonal corners.
4. Do NOT connect the P1_BASE and M5Stack CoreInk, before sending, since they will not fit in a standard [PostNL brievenbusdoos](https://shop.postnl.nl/webshop/verpakkingen/brievenbusdoos-a5-255x160x28mm) when stacked.

[^2]: By pre-connecting the RJ12 cable to connector `J2` on the PCB, you help users at home avoid installation errors. You may even consider clipping off 3 to 4 mm from the latch of the modular conector. After insertion the connector does not protrude from the female connecto, which clearly signals to the user that this cable should not be deinstalled. 

After receiving the device in a home:
1. Connect to the P1-BASE to the based of the M5Stack CoreInk, ensuring alignment of M5Stack CoreInk with the P1-BASE; the LEGO pins will help make sure that the 2x8 pin connector of the P1-BASE properly connects to M5Stack CoreInk.
2. Unplug your existing smart meter reader (if any) from the P1 port smart meter
3. Connect the plug of the NeedForHeat smart meter module in the P1 port .
4. Plug the RJ16 connector of our existing smart meter reader into the bottom RJ12 socket of the P1-BASE.

### Setting the DIP Switches

The hardware version v2.7 (2024-06-07) features 3 DIP switches on the PCB to control data request line management. Adjust the switches according to the following settings before delivering the device to the user:

| DIP-switch Number | ON Position                                        | OFF Position                                          |
| ----------------- | -------------------------------------------------- | ----------------------------------------------------- |
| 1                 | Data requested continuously (DSMR 4 & 5)           | Data not requested continuously                       |
| 2                 | Data request driven by M5Stack CoreInk             | Data request from M5Stack CoreInk ignored             |
| 3                 | Data request driven by external smart meter reader | Data request from external smart meter reader ignored |

If multiple DIP switches are ON simultaneously, data is requested if any corresponding source requires it. This may cause the external smart meter reader to receive partial messages, but according to the [DSMR P1 Port Companion Standard](https://github.com/energiegedrag-nl/dsmr-info?tab=readme-ov-file#dsmr-versions-standards) since version 3.0, smart meter readers should be able to handle partial messages.

 
## Developing

### Printed Circuit Board
To change the hardware design of the PCB, you need:
* [KiCad version 8.0.0 or later](https://www.kicad.org/download/) installed to change te PCB design. 

The KiCad source files of the PCB can be found in the folder [pcb](./pcb).

To convert the PCBs into a format suitable for fabrication, consult the webpage of your PCB manufacturer of choice. For example, see the [JLCPCB guide on how to export Gerbers](https://support.jlcpcb.com/article/149-how-to-generate-gerber-and-drill-files-in-kicad) and the  [JLCPCB guide how to export the BOM and POS files](https://support.jlcpcb.com/article/84-how-to-generate-the-bom-and-centroid-file-from-kicad). You may also use a KiCad plug-in for this purpose such as [kicad-jlcpcb-tools](https://github.com/Bouni/kicad-jlcpcb-tools).

<!-- 
### Enclosure
To change the hardware design of the enclosure, you need either:
* [Autodesk Fusion 360](https://www.kicad.org/download/) installed (Autodesk provides 30 day free trials and [free one-year educational access](https://www.autodesk.com/education/edu-software/overview?sorting=featured&filters=individual) to its products and services for eligible students, teachers and research staff); 
* or [FreeCAD](https://www.freecadweb.org/), an open source alternative.

The source files of the enclosure can be found in the folder [enclosure](./enclosure). We include both .f3d source files and .step source files we obtained after conversion.
-->

## Features

The NeedForHeat P1-BASE includes the following main hardware components:

- [x] Built-in P1-splitter for connecting an additional smart meter reader to the lower female RJ12 connector (`J3`).
- [x] Integrated [Schmitt trigger](https://en.wikipedia.org/wiki/Schmitt_trigger) to reduce signal noise.
- [x] 3 DIP-switches on the PCB for enabling/disabling data request line management.
- [x] Bottom-side 2x8 pin header for MI-BUS connection to the [M5Stack CoreInk](https://docs.m5stack.com/en/core/coreink) (requires soldering yourself, or a hefty JLCPCB fee for bottom-side hand-soldering).

To-do:

- [ ] Test compatibility with Landis+Gyr E360 series smart meters (e.g., [Landis+Gyr CD2D](https://www.landisgyr.eu/), [CM3D](https://www.landisgyr.eu/)).
- [ ] Consider using 'upside-down' RJ12 female connectors for easier [M5Stack CoreInk](https://docs.m5stack.com/en/core/coreink) screen readability.
- [ ] Evaluate relocating and optimizing the 2x8 pin header from the bottom side to the top side of the PCB to reduce manufacturing costs. 
  > (This would also obviate the need for 'upside-down' RJ12 female connectors, above.)
- [ ] Refine PCB design to reduce clutter where possible.
- [ ] Experiment with alternative data request management methods (e.g., MOSFETs, BJTs), which would allow the [M5Stack CoreInk](https://docs.m5stack.com/en/core/coreink) to check and control data request management in software.
- [ ] Implement low-power LEDs for indicating power status, data request status, and data flow.
- [ ] Develop energy-efficient charging strategies for the [M5Stack CoreInk](https://docs.m5stack.com/en/core/coreink) 390 mAh LiPo battery from DSMR 4 and DSMR 5 smart meters, without triggering the fold-back current limiting feature of some smart meters.
- [ ] Design a 3D-printable enclosure compatible with the [M5Stack CoreInk](https://docs.m5stack.com/en/core/coreink), potentially using [LEGO connector pens](https://www.blokjeskoning.nl/product/pen-stroef-pen-stroef-zwart/). A preliminary version can be found in the [needforheat-boiler-monitor-hardware repository](https://github.com/energiegedrag-nl/needforheat-boiler-monitor-hardware).


## Status
Project is:  _in progress_

## License
The hardware designs in this repository are available under the [CERN-OHL-P v2 license](./LICENSE), Copyright 2024 [Research group Energy Transition, Windesheim University of Applied Sciences](https://windesheim.nl/energietransitie)

## Citation

If you use this repository in your research or work, please cite the following pre-print, which describes the overall NeedForHeat DataGear system of which this repository is a part:

> Ter Hofte, H., & van Ravenzwaaij, N. (2025). *NeedForHeat DataGear: An Open Monitoring System to Accelerate the Residential Heating Transition*. arXiv preprint arXiv:2509.06927. https://doi.org/10.48550/arXiv.2509.06927

**Note:** This is a pre-print submitted on 8 Sep 2025 and has not yet been peer-reviewed. For the full paper, see [https://arxiv.org/abs/2509.06927](https://arxiv.org/abs/2509.06927).

## Credits
This open hardware design is a collaborative effort of:
* Rick de Graaf · [@277r](https://github.com/277r) 
* Gerwin ten Have · [@GerwintenHave](https://github.com/GerwintenHave) 

Product owners:
* Henri ter Hofte · [@henriterhofte](https://github.com/henriterhofte)
* Marco Winkelman · [@MarcoW71](https://github.com/MarcoW71)

We use and gratefully acknowlegde the efforts of the makers of:
* [Twomes P1 Gateway Hardware](https://github.com/energiegedrag-nl/twomes-p1-gateway-hardware), by Research group Energy Transition at Windesheim University of Applied Sciences, licenced under Apache 2.0
* [KiCad Libraries](https://kicad.github.io/), by the KiCad Development Team, licensed under [an adapted version of the CC-BY-SA 4.0 License](https://www.kicad.org/libraries/license/)
