# dshot-esc-100a

A 12 V, 100 A three-phase **all-N-channel** motor driver for a high-power
drone motor, controllable over **DShot150/300/600/1200**.

| | |
|---|---|
| Battery | 3S LiPo, 9.0–12.6 V (operating range 6–16 V) |
| Continuous | **100 A** (~1.2 kW) |
| Burst | **150 A** for 10 s |
| Bridge | 6 switch positions × **2 paralleled N-channel MOSFETs = 12 total** |
| Gate driver | **DRV8323R** (RS or RH — one footprint, both variants) |
| Controller | **STM32G071CBT6** running **AM32** |
| Control | DShot150/300/600/1200, bidirectional, + ESC telemetry |
| Efficiency | ~98.5 % at 100 A (≈19 W dissipated) |

**Status: schematic complete, ERC-clean, 160 components. PCB layout not
started.**

---

## Why all N-channel, and how the high side is driven

A P-channel high-side switch is the easy way to build a bridge and the
wrong way here — P-channel parts with usable R_DS(on) at 100 A don't exist
in a sane package. Both rails are N-channel, so the high-side gate has to
be driven above the battery rail.

The DRV8323R does that with an on-chip **charge pump**, not a bootstrap
capacitor. A bootstrap cap must be refreshed by pulling the phase node
low, which caps duty cycle below 100 %. A charge pump holds the gate up
indefinitely, so the high-side FET stays fully enhanced at **100 % duty** —
exactly the regime "drive it hard" lives in.

## Shoot-through: four independent layers

Shoot-through at 12 V into 2 × 0.43 mΩ is roughly **14 kA**, limited only
by parasitics. It destroys the bridge in microseconds and no fuse is fast
enough. So it's prevented four times over, and no single layer is trusted:

| Layer | Mechanism | Independent of |
|---|---|---|
| 1 | TIM1 hardware dead-time generator, **625 ns** | firmware timing bugs |
| 2 | DRV8323R cross-conduction lockout + 100 ns | the MCU entirely |
| 3 | 6 × SN74LVC1G97 combinational interlock | MCU *and* driver |
| 4 | Gate-source pulldowns + per-FET series gate resistors | everything active |
| 0 | `nFAULT` → `TIM1_BKIN` kills all 6 outputs in hardware | firmware latency |

The dead-time budget works out **negative** under nominal conditions —
because sink current is set 3.5× source current, the outgoing FET is
already off before the incoming one conducts. The 625 ns is therefore pure
margin against V_th spread, tempco, and gate ringing. Full derivation from
the FET's measured gate charge: **[`docs/shoot-through.md`](docs/shoot-through.md)**.

## Documentation

| Document | What's in it |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | topology, block diagram, sheet map, design decisions |
| [`docs/shoot-through.md`](docs/shoot-through.md) | the four layers, dead-time budget, DTG encoding |
| [`docs/power-budget.md`](docs/power-budget.md) | conduction/switching/shunt losses, thermals, why 2 FETs not 3 |
| [`docs/pinout.md`](docs/pinout.md) | full 48-pin MCU map + AM32 hardware group |
| [`docs/gate-driver-config.md`](docs/gate-driver-config.md) | RH vs RS dual build, every register value derived |
| [`docs/references.md`](docs/references.md) | every datasheet and firmware source used |
| [`firmware/README.md`](firmware/README.md) | AM32 target, SPI init, flashing, **bring-up order** |
| [`manufacturing/BOM.md`](manufacturing/BOM.md) | generated from the netlist, real LCSC numbers |
| [`manufacturing/dshot-esc-100a/ISSUES.md`](manufacturing/dshot-esc-100a/ISSUES.md) | 12 open items — read before fabricating |

## Repository layout

```
design/          GENERATED KiCad 10 project — never save from the GUI
  01_power_in  02_gate_driver  03_power_stage
  04_mcu       05_sense        06_protection
  lib/         DRV8323R + STM32G071CBTx symbols
scripts/        the source of truth for everything in design/
  gen_custom_symbols.py  gen_project.py  wire_sheets.py
  verify_project.py      gen_bom.py      calc_*.py
  kicad_sch.py           kicad_symlib.py
docs/           design documentation
firmware/       AM32 target + DRV8323RS SPI driver
datasheets/     22 PDFs, synced from LCSC
manufacturing/  BOM, schematic PDF, issue tracker
```

## Reproducing the design

```bash
pgrep -fil kicad                            # must be empty first
python3 scripts/gen_custom_symbols.py       # symbol library
python3 scripts/gen_project.py --verify     # refuses to write if broken
python3 scripts/gen_project.py              # sheets + placement + wiring
python3 scripts/gen_bom.py
python3 scripts/verify_project.py           # the real gate
```

The calculations behind the docs are runnable, not asserted:

```bash
python3 scripts/calc_deadtime.py    # DTG table + dead-time budget
python3 scripts/calc_power.py       # loss and thermal budget
```

## Before you build one

Read [`ISSUES.md`](manufacturing/dshot-esc-100a/ISSUES.md). The three that
block fabrication:

- **ESC-004** — the high-current terminals still use a 2.5 mm² placeholder
  footprint, good for ~25 A, not 100 A.
- **ESC-001** — the input ripple budget (~50 A RMS) isn't closed.
- **ESC-012** — 19 W into ~50 × 35 mm is **not** passively coolable; this
  design assumes forced air.

And follow the bring-up order in `firmware/README.md`. Do not put a motor
on this board first.

## Licence

Hardware: CERN-OHL-S v2. Firmware snippets: MIT, matching AM32.
