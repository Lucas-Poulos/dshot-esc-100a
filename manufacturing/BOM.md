# Bill of materials

Generated from the schematic netlist by `scripts/gen_bom.py` on 2026-09-25. Do not edit by hand -- regenerate.

**43 distinct lines, 160 placements.** The schematic is fully wired and ERC-clean, so these quantities are real rather than provisional.

Prices and stock are deliberately absent -- they go stale within days. Refresh before a BOM lock with the `lcsc` skill.

---

## Sourcing notes

**The gate driver is the line to watch.** The design is laid out for both DRV8323R variants on one footprint -- only pins 29-32 differ (SLVSDJ3D Table 6-4):

| Part | LCSC | Stock | Price | Configured by |
|---|---|---:|---:|---|
| `DRV8323RSRGZT` | C2653553 | ~67 | $4.29 | SPI, from the MCU |
| `DRV8323RHRGZR` | C543035 | ~2338 | $2.39 | resistors R203-R206 |

RS is the default because it can set source and sink gate current independently, which is what produces the turn-off/turn-on asymmetry the dead-time budget relies on. RH cannot -- one pin sets both. An RH build is still safe but has less margin, and its resistor values are **not yet transcribed** (issue ESC-010). See `docs/gate-driver-config.md` before substituting.

Everything else is commodity: no part below has under ~1000 pieces at LCSC, and the FETs, MCU and logic all have multiple sources.

---

## Lines

| Qty | MPN | LCSC | Value | Package | Refs | Sheets |
|----:|-----|------|-------|---------|------|--------|
| 29 | `FRC0603F1002TS` | `C2906982` | 10k | R_0603_1608Metric | R202, R211, R313, R314, ... (+25) | Gate Driver, MCU, Power Stage, Protection, Sense |
| 26 | `GRM32DR71E106KA12L` | `C77100` | 10u | C_1210_3225Metric | C104, C105, C106, C107, ... (+22) | Gate Driver, Power Input |
| 12 | `FRC0805F4R70TS` | `C2933459` | 4.7 | R_0805_2012Metric | R301, R302, R303, R304, ... (+8) | Power Stage |
| 12 | `TPHR8504PL,L1Q(M` | `C5331611` | TPHR8504PL | PQFN-8-EP_6x5mm_P1.27mm_Generic | Q301, Q302, Q303, Q304, ... (+8) | Power Stage |
| 11 | `CC0603KRX7R9BB104` | `C14663` | 100n | C_0603_1608Metric | C203, C401, C402, C501, ... (+7) | Gate Driver, MCU, Protection, Sense |
| 7 | `B5819W SL` | `C8598` | B5819W | D_SOD-123 | D201, D301, D302, D303, D304, D305, D306 | Gate Driver, Power Stage |
| 6 | `RCA030RLF` | `C22356631` | 0 | R_0603_1608Metric | R325, R326, R327, R328, R329, R330 | Power Stage |
| 6 | `RCA030RLF` | `C22356631` | 0R BYP | R_0603_1608Metric | R601, R602, R603, R604, R605, R606 | Protection |
| 6 | `SN74LVC1G97DBVR` | `C128411` | SN74LVC1G97 | SOT-23-6 | U601, U602, U603, U604, U605, U606 | Protection |
| 5 | `FRC0603F1001TS` | `C2907002` | 1k | R_0603_1608Metric | R402, R504, R505, R506, R510 | MCU, Sense |
| 4 | `HoJLR2512-3W-1mR-1%` | `C2903470` | 1m | R_2512_6332Metric | RS301, RS302, RS303, RS304 | Power Stage |
| 3 | `SPZ1EM331F11O00R` | `C160677` | 330u/25V | CP_Radial_D8.0mm_P3.50mm | C101, C102, C103 | Power Input |
| 2 | `0603WAF1003T5E` | `C25803` | 100k | R_0603_1608Metric | R210, R511 | Gate Driver, Sense |
| 2 | `CL21B475KAFNNNE` | `C98195` | 4.7u | C_0805_2012Metric | C207, C403 | Gate Driver, MCU |
| 1 | `-` | `-` | PHASE_A | SolderWire-2.5sqmm_1x01_D2.4mm_OD3.6mm_Relief | J301 | Power Stage |
| 1 | `-` | `-` | PHASE_B | SolderWire-2.5sqmm_1x01_D2.4mm_OD3.6mm_Relief | J302 | Power Stage |
| 1 | `-` | `-` | PHASE_C | SolderWire-2.5sqmm_1x01_D2.4mm_OD3.6mm_Relief | J303 | Power Stage |
| 1 | `-` | `-` | SWD | PinHeader_2x05_P1.27mm_Vertical | J401 | MCU |
| 1 | `-` | `-` | SIGNAL | PinHeader_1x04_P2.54mm_Vertical | J402 | MCU |
| 1 | `-` | `-` | VBAT+ | SolderWire-2.5sqmm_1x01_D2.4mm_OD3.6mm_Relief | J101 | Power Input |
| 1 | `-` | `-` | VBAT- | SolderWire-2.5sqmm_1x01_D2.4mm_OD3.6mm_Relief | J102 | Power Input |
| 1 | `CC0603KRX7R9BB104` | `C14663` | 100n/16V | C_0603_1608Metric | C205 | Gate Driver |
| 1 | `CC0603KRX7R9BB104` | `C14663` | 100n VREF+ | C_0603_1608Metric | C404 | MCU |
| 1 | `CC0603KRX7R9BB104` | `C14663` | 100n NRST | C_0603_1608Metric | C406 | MCU |
| 1 | `CC0603KRX7R9BB104` | `C14663` | 100n VREF | C_0603_1608Metric | C503 | Sense |
| 1 | `CL10B105KA8NNNC` | `C29936` | 1u/25V | C_0603_1608Metric | C202 | Gate Driver |
| 1 | `CL10B105KA8NNNC` | `C29936` | 1u | C_0603_1608Metric | C208 | Gate Driver |
| 1 | `CL10B105KA8NNNC` | `C29936` | 1u VREF+ | C_0603_1608Metric | C405 | MCU |
| 1 | `CL10B473KB8NNNC` | `C1622` | 47n/50V | C_0603_1608Metric | C201 | Gate Driver |
| 1 | `DRV8323RSRGZT` | `C2653553` | DRV8323RS | Texas_RGZ0048A_VQFN-48-1EP_7x7mm_P0.5mm_EP5.15x5.15mm_ThermalVias | U201 | Gate Driver |
| 1 | `FRC0603F1002TS` | `C2906982` | IDRIVE | R_0603_1608Metric | R203 | Gate Driver |
| 1 | `FRC0603F1002TS` | `C2906982` | VDS | R_0603_1608Metric | R204 | Gate Driver |
| 1 | `FRC0603F1002TS` | `C2906982` | MODE | R_0603_1608Metric | R205 | Gate Driver |
| 1 | `FRC0603F1002TS` | `C2906982` | GAIN | R_0603_1608Metric | R206 | Gate Driver |
| 1 | `FRC0603F1002TS` | `C2906982` | 10k SDO | R_0603_1608Metric | R207 | Gate Driver |
| 1 | `FRC0603F1002TS` | `C2906982` | 10k nFAULT | R_0603_1608Metric | R208 | Gate Driver |
| 1 | `FRC0603F1002TS` | `C2906982` | 10k EN pd | R_0603_1608Metric | R209 | Gate Driver |
| 1 | `FRC0603F3322TS` | `C2933200` | 33.2k | R_0603_1608Metric | R201 | Gate Driver |
| 1 | `NCP18XH103F03RB` | `C13564` | 10k NTC | R_0603_1608Metric | R513 | Sense |
| 1 | `SLS6D38S330MTT` | `C364136` | 33u | L_7.3x7.3_H3.5 | L201 | Gate Driver |
| 1 | `SMBJ20A` | `C364296` | SMBJ20A | D_SMB | D101 | Power Input |
| 1 | `STM32G071CBT6` | `C432212` | STM32G071CBT6 | LQFP-48_7x7mm_P0.5mm | U401 | MCU |
| 1 | `XL-1608UGC-04` | `C965804` | green | LED_0603_1608Metric | D401 | MCU |

---

## Lines needing attention

| MPN | Note |
|---|---|
| `GRM32DR71E106KA12L` | 24 off. Derates to ~5-6 uF at 12 V bias - ESC-001 |
| `TPHR8504PL,L1Q(M` | 12 off, 2 per switch position. 40 V on a 12.6 V bus is deliberate - see docs/architecture.md |
| `SN74LVC1G97DBVR` | Shoot-through interlock. Wired per SCES416N Fig 6 |
| `HoJLR2512-3W-1mR-1%` | 4 in parallel = 0.25 mOhm. Needs a Kelvin sense tap in layout - ESC-005 |
| `SPZ1EM331F11O00R` | Through-hole radial. ~2.8 A ripple each - ESC-001 |
| `DRV8323RSRGZT` | SPI variant. RH (C543035) is pin-compatible - see docs/gate-driver-config.md before substituting |
| `STM32G071CBT6` | 48-pin part is REQUIRED: it is the only one that frees PB12/TIM1_BKIN. Symbol is KiCad's G081CBTx renamed |

## Before ordering

1. Wire the schematic -- quantities here are pre-wiring estimates.
2. Refresh stock for every line; flag anything under 10x requirement.
3. Record a second-source C-number for each thin line in that part's `manufacturing/parts/{Vendor}/{MPN}/{MPN}.md`.
4. Resolve everything in `manufacturing/stm32mp157-devkit/ISSUES.md` or defer it explicitly.
5. Re-run `python3 scripts/verify_project.py`.
6. Re-check stock immediately before placing the order -- do not order against numbers from a previous session.

