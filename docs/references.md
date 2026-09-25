# References

Every datasheet fact in this repo traces to one of these. Where a figure is
still assumed rather than read, it carries an `ESC-NNN` issue number.

## Primary datasheets (PDFs in `datasheets/`, manifest in `datasheets/manifest.json`)

| Part | Document | Used for |
|---|---|---|
| **DRV8323R** | TI **SLVSDJ3D** rev D, Mar 2022 — *DRV832x 6-to-60-V Three-Phase Smart Gate Driver* | Table 6-4 (48-pin RGZ pinout, RH vs RS), Figure 9-1 (application circuit), Eq. 9-12 (charge-pump and IDRIVE sizing), Eq. 17 (VDS OCP), Tables 8-15…8-19 (register map), §10.2 (bulk capacitance) |
| **STM32G071CB** | ST **DS12232** — *STM32G071x8/xB* | 48-pin LQFP pinout, alternate-function tables (ESC-002, ESC-003) |
| **STM32G0 series** | ST **RM0444** — reference manual | TIM1 `BDTR.DTG` dead-time encoding, COMP2 input routing, SYSCFG PA11/PA12 remap |
| **TPHR8504PL** | Toshiba — *N-channel 40 V 340 A MOSFET, SOP Advance* | Qg = 103 nC, Qgs1 = 25 nC, Qgd = 12.4 nC, R_DS(on) = 0.85 mΩ max @ V_GS = 10 V |
| **SN74LVC1G97** | TI **SCES416N** rev N, Jan 2017 | Table 1 function table, Figure 6 (`In0` = GND ⇒ `Y = In1 AND NOT In2`), SOT-23 pinout |
| **LMR16006X** | TI **SNVSA13** | buck feedback reference and external component sizing (ESC-007) — the DRV8323R's integrated buck is this converter |
| SMBJ20A | LCSC datasheet | 20 V standoff, 24.5 V breakdown, 32.4 V clamp |
| B5819W | LCSC datasheet | 40 V 1 A Schottky, buck catch diode and gate turn-off bypass |

## Firmware

| Source | Used for |
|---|---|
| [am32-firmware/AM32](https://github.com/am32-firmware/AM32) | DShot implementation, target model |
| `Inc/targets.h` | `HARDWARE_GROUP_G0_A` pin map; `AIKON_04_G071` as the precedent for `NO_PA11_PA12_REMAP` on a 48-pin G071 |
| `Mcu/g071/Src/peripherals.c` | clock tree (HSI 16 MHz → PLL ×8 ÷2 = 64 MHz), `TIM1` init (PSC = 0, CKD = DIV1 ⇒ t_DTS = 15.625 ns), `COMP2` GPIO comment (`PA2 → COMP2_INM`, `PA3 → COMP2_INP`), `LL_SYSCFG_EnablePinRemap` default |
| `Mcu/g071/Src/comparator.c` | phase multiplexing onto one comparator, `LL_COMP_INPUT_PLUS_IO3` as the virtual neutral |
| `Mcu/g071/Src/serial_telemetry.c` | USART1 one-wire telemetry on PB6, AF0, 115200 |
| [AM32 wiki](https://wiki.am32.ca/) | supported MCU list, bootloader/flashing procedure |

## KiCad libraries used

| Item | Source | Note |
|---|---|---|
| `Texas_RGZ0048A_VQFN-48-1EP_7x7mm_P0.5mm_EP5.15x5.15mm_ThermalVias` | KiCad `Package_DFN_QFN` | TI's own RGZ land pattern — exactly the DRV8323R package |
| `PQFN-8-EP_6x5mm_P1.27mm_Generic` | KiCad `Package_DFN_QFN` | its own description lists "Toshiba SOP Advance" among the compatible packages |
| `LQFP-48_7x7mm_P0.5mm` | KiCad `Package_QFP` | STM32G071CBT6 |
| `Transistor_FET:Q_NMOS_SSSGD_AvalancheRated` | KiCad stock | S = pads 1-3, G = 4, D = 5 — matches the PQFN-8 land pattern |
| `74xGxx:74LVC1G97` | KiCad stock | `extends 74LVC1G57`; flattened by `kicad_sch.py::_merge_extends` |
| `MCU_ST_STM32G0:STM32G081CBTx` | KiCad stock | copied and renamed to `STM32G071CBTx` — same die and bonding, DS12232 covers both |

## Design references consulted

- TI **SLVA504** / *Architecture for Brushless-DC Gate Drive Systems* — referenced from SLVSDJ3D §5 for the device-family comparison.
- The four-layer shoot-through argument, the paralleled-FET gate-resistor
  rule, and the charge-pump-limits-parallel-count result are derived in
  `docs/shoot-through.md` and `docs/power-budget.md` from the datasheet
  figures above, not taken from a secondary source.

## A note on one source that was wrong

An automated fetch of the SN74LVC1G97 datasheet returned a pin assignment
(`pin 3 = C, pin 5 = B, pin 6 = VCC`) and a configuration table that
contradicted both KiCad's symbol and the device's own logic diagram — its
"inverter" configuration evaluates to a buffer. Reading the PDF directly
gave `In0 = 3, Y = 4, VCC = 5, In2 = 6` and Table 1 above. **The interlock
in `06_protection.kicad_sch` is wired from the PDF, not the summary.**
