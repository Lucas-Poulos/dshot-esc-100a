# dshot-esc-100a — Session Briefing

## What this is

A 12 V / 100 A three-phase all-N-channel motor driver (drone ESC) with
12 MOSFETs (2 per switch position), a DRV8323R smart gate driver, an
STM32G071CBT6 running AM32, and DShot input.

**Schematic is complete, wired, and ERC-clean at 0 violations. PCB layout
has not started.**

| Item | Choice | Why |
|---|---|---|
| Gate driver | `DRV8323R` VQFN-48 RGZ | charge pump ⇒ 100 % duty; programmable dead time; 3 CSAs; 600 mA buck. RS and RH share one footprint |
| MCU | `STM32G071CBT6` LQFP-48 | **only** package that frees PB12/TIM1_BKIN; cheaper and better stocked than the 32-pin |
| FET | `TPHR8504PL` 40 V / 0.85 mΩ | 40 V on a 12.6 V bus is margin against switch-node ringing |
| Interlock | 6 × `SN74LVC1G97` | TI Figure 6 tie-off ⇒ `Y = In1 AND NOT In2` |

---

## Ground rules

### design/ is generated — edit the scripts, not the output

```bash
pgrep -fil kicad     # MUST be empty before running any generator

python3 scripts/gen_custom_symbols.py   # symbol library (self-normalising)
python3 scripts/gen_project.py --verify # gate: refuses to write on failure
python3 scripts/gen_project.py          # sheets + placement + wiring
python3 scripts/gen_bom.py
python3 scripts/verify_project.py       # ALWAYS finish with this
```

Generators use `uuid5`, so re-running produces byte-identical files and
diffs stay readable. `gen_custom_symbols.py` ends by running
`kicad-cli sym upgrade --force` on its own output, so the library is
byte-identical to what KiCad itself would write — **verified idempotent**.

**Opening the project read-only is fine. Saving from the GUI is not.**

### Wiring lives in `wire_sheets.py`

Nets are made by **name**: each pin gets a stub and a label, and
identically spelled labels are one net. KiCad's netlister treats that as
identical to drawn polylines, and hand-routing a 12-MOSFET bridge is not
tractable.

Rail names are module-level constants precisely because a misspelled rail
silently becomes a second net that looks completely normal on screen.

### A clean ERC is a red flag until you've proven ERC is live

This project currently reports **0 violations**, which on a 160-part board
is exactly the result you should distrust. `verify_project.py` check 5
therefore does not just read the ERC report — it copies the design, deletes
the `+3V3` `PWR_FLAG`, re-runs ERC, and **fails if that does not produce a
violation**. A clean ERC only counts when ERC has been shown to be live.

The failure mode that motivates this: **a malformed `lib_symbols` entry
produces a file whose parens balance perfectly but which KiCad silently
refuses to load.** The root sheet then opens *without that sheet* and
reports nothing. Verify by netlisting and counting per sheet:

```bash
kicad-cli sch export netlist --format kicadxml --output /tmp/esc.xml \
    design/dshot-esc-100a.kicad_sch
# expect 160 components across exactly 6 sheets, 96 nets
```

`verify_project.py` check 1 does exactly this, per sheet.

### Never invent an LCSC part number

Every `Cxxxxx` here was resolved against LCSC:

```bash
python3 ~/.claude/skills/lcsc/scripts/search_lcsc.py <MPN or Cxxxxx>
```

If the API is down, leave `TBD` and open an issue. A wrong C-number means
wrong parts arrive.

### Don't trust a summarised datasheet

An automated fetch of the SN74LVC1G97 datasheet returned a **wrong** pin
assignment and a self-contradictory configuration table (its "inverter"
config evaluates to a buffer). The interlock is wired from the PDF's own
Table 1 and Figure 6. Read the PDF; the datasheets are in `datasheets/`.

---

## The two facts most likely to be got wrong

**1. `DEAD_TIME` is a register value, not nanoseconds.** AM32 writes it
straight into TIM1 `BDTR.DTG[7:0]`. With TIM1 at 64 MHz, PSC = 0, CKD =
DIV1, `t_DTS` = 15.625 ns, so `DEAD_TIME 40` = **625 ns**. Above 127 the
encoding changes slope, which is why AM32's `DT210` target is 6.25 µs and
not anything linear. `scripts/calc_deadtime.py` has the full table.

**2. `NO_PA11_PA12_REMAP` is mandatory here.** On the 48-pin G071, PA9 and
PA10 are *dedicated* pins 29 and 32; pins 33/34 are PA11/PA12. AM32 remaps
PA11/PA12 onto PA9/PA10 by default — correct for 28/32-pin parts, wrong
here. Without the define, the three high-side PWM outputs drive pads this
board leaves unconnected and the motor never spins. Precedent:
`AIKON_04_G071`.

---

## Current state

- [x] 6 hierarchical sheets, 160 components, fully wired
- [x] ERC 0 violations (and ERC proven live)
- [x] All 49 DRV8323R pads, all 48 MCU pins, all 12 FETs' 5 pads in the netlist
- [x] DRV8323R symbol from SLVSDJ3D Table 6-4; MCU symbol from KiCad's G081CBTx
- [x] Every part has Footprint + MPN + LCSC; 22 datasheets synced
- [x] AM32 target + bit-banged DRV8323RS SPI init
- [x] Analyzer: 42 findings, 0 errors, 0 warnings

### Next

- [ ] **ESC-004** custom high-current terminal footprint — blocks the PCB
- [ ] **ESC-010** transcribe the RH resistor level tables (SLVSDJ3D §8.5)
- [ ] **ESC-007** verify the buck feedback reference against SNVSA13
- [ ] **ESC-002 / ESC-003** confirm SPI and TIM1_BKIN AFs against DS12232
- [ ] 4-layer 2 oz stackup + a `.kicad_dru` written for THIS board, then layout

Full list: `manufacturing/dshot-esc-100a/ISSUES.md`.

## Useful commands

```bash
python3 scripts/calc_deadtime.py     # dead-time budget + DTG table
python3 scripts/calc_power.py        # loss and thermal budget

kicad-cli sch erc --output /tmp/erc.rpt --severity-all \
    design/dshot-esc-100a.kicad_sch
kicad-cli sch export pdf --output manufacturing/schematic.pdf \
    design/dshot-esc-100a.kicad_sch

python3 ~/.claude/skills/kicad/scripts/analyze_schematic.py \
    design/dshot-esc-100a.kicad_sch --analysis-dir analysis/
```
