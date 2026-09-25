#!/usr/bin/env python3
"""Generate the project-local symbol library: design/lib/dshot-esc-100a.kicad_sym

Two symbols, for two different reasons.

DRV8323R
    KiCad 10 ships no DRV83xx smart gate driver at all (Driver_Motor has
    DRV8308/8311/8412/8434/8461 and nothing else), so this is built from
    scratch. Every pin below is transcribed from **Table 6-4, "Pin
    Functions - 48-Pin DRV8323R Devices"** of the DRV832x datasheet
    SLVSDJ3D (rev D, March 2022), pages 10-11.

    This board is a dual RH/RS build. Table 6-4 gives both columns and
    they are identical for 44 of the 48 pins -- **only pins 29-32 differ**:

        pin   DRV8323RH        DRV8323RS
        29    MODE             SDO
        30    IDRIVE           SDI
        31    VDS              SCLK
        32    GAIN             nSCS

    Those four carry both names in the symbol, because the schematic has
    to show both the resistor network and the SPI routing.

STM32G071CBTx
    KiCad has E/G/K/R-package G071 symbols but no C (48-pin) one. It does
    have STM32G081CBTx, and the G081CB is the same die and the same
    package bonding as the G071CB -- ST documents both in DS12232, and the
    difference is the AES accelerator, which has no pins. So rather than
    hand-transcribing 48 pins (and risking a transcription error on a
    board where a swapped PWM pin destroys the bridge), the stock symbol
    is copied and renamed.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from kicad_symlib import Pin, Unit, emit_symbol, upsert, split_symbols

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "design" / "lib" / "dshot-esc-100a.kicad_sym"
STOCK = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols")

DS_DRV = "https://www.ti.com/lit/ds/symlink/drv8323.pdf"
DS_STM = "https://www.st.com/resource/en/datasheet/stm32g071cb.pdf"

FP_DRV = ("Package_DFN_QFN:Texas_RGZ0048A_VQFN-48-1EP_7x7mm_P0.5mm"
          "_EP5.15x5.15mm_ThermalVias")
FP_STM = "Package_QFP:LQFP-48_7x7mm_P0.5mm"

# --------------------------------------------------------------------------
# DRV8323R -- SLVSDJ3D Table 6-4. (name, pad, electrical type)
# --------------------------------------------------------------------------

# Unit A: gate drive + charge pump + power. The high-current half.
UNIT_A_LEFT = [
    Pin("VM", "6", "power_in"),
    Pin("VDRAIN", "7", "input"),
    Pin("VCP", "5", "passive"),
    Pin("CPH", "4", "passive"),
    Pin("CPL", "3", "passive"),
    Pin("PGND", "2", "power_in"),
]
UNIT_A_RIGHT = [
    Pin("GHA", "8", "output"),
    Pin("SHA", "9", "bidirectional"),
    Pin("GLA", "10", "output"),
    Pin("GHB", "17", "output"),
    Pin("SHB", "16", "bidirectional"),
    Pin("GLB", "15", "output"),
    Pin("GHC", "18", "output"),
    Pin("SHC", "19", "bidirectional"),
    Pin("GLC", "20", "output"),
]

# Unit B: the three current-shunt amplifiers.
UNIT_B_LEFT = [
    Pin("SPA", "11", "input"),
    Pin("SNA", "12", "input"),
    Pin("SPB", "14", "input"),
    Pin("SNB", "13", "input"),
    Pin("SPC", "21", "input"),
    Pin("SNC", "22", "input"),
]
UNIT_B_RIGHT = [
    Pin("SOA", "25", "output"),
    Pin("SOB", "24", "output"),
    Pin("SOC", "23", "output"),
    Pin("VREF", "26", "power_in"),
    Pin("CAL", "34", "input"),
    Pin("AGND", "35", "power_in"),
]

# Unit C: logic inputs, config/SPI, the buck regulator, grounds.
UNIT_C_LEFT = [
    Pin("INHA", "37", "input"),
    Pin("INLA", "38", "input"),
    Pin("INHB", "39", "input"),
    Pin("INLB", "40", "input"),
    Pin("INHC", "41", "input"),
    Pin("INLC", "42", "input"),
    Pin("ENABLE", "33", "input"),
    Pin("nFAULT", "28", "open_collector"),
]
UNIT_C_RIGHT = [
    # pins 29-32: RH name / RS name (Table 6-4)
    Pin("MODE/SDO", "29", "bidirectional"),
    Pin("IDRIVE/SDI", "30", "input"),
    Pin("VDS/SCLK", "31", "input"),
    Pin("GAIN/nSCS", "32", "input"),
    Pin("DVDD", "36", "power_out"),
    Pin("VIN", "47", "power_in"),
    Pin("SW", "45", "output"),
    Pin("CB", "44", "passive"),
    Pin("FB", "1", "input"),
    Pin("nSHDN", "48", "input"),
    Pin("NC", "46", "no_connect"),
]
UNIT_C_BOTTOM = [
    Pin("DGND", "27", "power_in"),
    Pin("BGND", "43", "power_in"),
    Pin("PAD", "49", "power_in"),
]

DRV_PROPS = {
    "Footprint": FP_DRV,
    "Datasheet": DS_DRV,
    "Description": ("6-60V three-phase smart gate driver, 3x CSA, "
                    "600mA buck, VQFN-48 RGZ"),
    "MPN": "DRV8323RSRGZT",
    "Manufacturer": "Texas Instruments",
    "LCSC": "C2653553",
    "MPN_ALT": "DRV8323RHRGZR",
    "LCSC_ALT": "C543035",
}


def build_drv() -> str:
    units = [
        Unit(left=UNIT_A_LEFT, right=UNIT_A_RIGHT),
        Unit(left=UNIT_B_LEFT, right=UNIT_B_RIGHT),
        Unit(left=UNIT_C_LEFT, right=UNIT_C_RIGHT, bottom=UNIT_C_BOTTOM),
    ]
    text, pinmaps = emit_symbol("DRV8323R", units, DRV_PROPS)
    return text, pinmaps


def build_stm() -> str:
    """Copy MCU_ST_STM32G0:STM32G081CBTx -> STM32G071CBTx."""
    src = (STOCK / "MCU_ST_STM32G0.kicad_sym").read_text()
    blocks = split_symbols(src)
    key = "STM32G081CBTx"
    if key not in blocks:
        sys.exit(f"FATAL: {key} not found in stock MCU_ST_STM32G0.kicad_sym")
    body = blocks[key]
    if "extends" in body.split("\n")[1]:
        sys.exit(f"FATAL: {key} uses 'extends'; must be flattened first")
    # Rename the symbol and its nested unit sub-symbols in one pass.
    body = body.replace("STM32G081CBTx", "STM32G071CBTx")
    # Point Value / Footprint / Datasheet at the part we actually order.
    body = re.sub(r'\(property "Footprint" "[^"]*"',
                  f'(property "Footprint" "{FP_STM}"', body, count=1)
    body = re.sub(r'\(property "Datasheet" "[^"]*"',
                  f'(property "Datasheet" "{DS_STM}"', body, count=1)
    return body


def normalize(path: Path) -> None:
    """Let KiCad itself rewrite the library into its canonical form.

    Our emitter produces semantically correct output, but KiCad sorts pins
    into its own order when it saves. Without this step the file churns
    every time anyone opens the library in the GUI, and a 400-line
    reordering diff hides real changes. Running the upgrade here makes the
    generator byte-idempotent against KiCad 10.0.5.

    Side effect: it rewrites (generator ...) to "kicad_symbol_editor",
    which is accurate -- the file is in that tool's format.
    """
    r = subprocess.run(["kicad-cli", "sym", "upgrade", "--force", str(path)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"FATAL: kicad-cli rejected the library:\n{r.stderr}")


def main() -> None:
    verify = "--verify" in sys.argv

    drv_text, pinmaps = build_drv()
    pads = []
    for unit in (UNIT_A_LEFT + UNIT_A_RIGHT + UNIT_B_LEFT + UNIT_B_RIGHT
                 + UNIT_C_LEFT + UNIT_C_RIGHT + UNIT_C_BOTTOM):
        pads.append(unit.number)

    ok = True
    if len(pads) != len(set(pads)):
        dupes = {p for p in pads if pads.count(p) > 1}
        print(f"FAIL: duplicate pads {sorted(dupes)}")
        ok = False
    expected = {str(n) for n in range(1, 50)}     # 48 pins + pad 49
    missing = expected - set(pads)
    extra = set(pads) - expected
    if missing:
        print(f"FAIL: missing pads {sorted(missing, key=int)}")
        ok = False
    if extra:
        print(f"FAIL: unexpected pads {sorted(extra)}")
        ok = False
    print(f"DRV8323R: {len(pads)} pads across 3 units "
          f"({'OK' if ok else 'BROKEN'})")

    stm_text = build_stm()
    n_stm = len(re.findall(r'\(number "', stm_text))
    if n_stm != 48:
        print(f"FAIL: STM32G071CBTx has {n_stm} pins, expected 48")
        ok = False
    print(f"STM32G071CBTx: {n_stm} pins (copied from STM32G081CBTx)")

    if not ok:
        sys.exit(1)
    if verify:
        print("\n--verify only, nothing written")
        return

    upsert(LIB, drv_text, "DRV8323R")
    upsert(LIB, stm_text, "STM32G071CBTx")
    normalize(LIB)
    print(f"\nwrote {LIB.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
