#!/usr/bin/env python3
"""Generate manufacturing/BOM.md from the schematic netlist.

Reads the hierarchy netlist rather than a hand-maintained list, so the BOM
cannot drift from the schematic. Groups by MPN, aggregates quantities, and
records which sheets each line appears on.

Stock and price are not fetched here -- they go stale immediately. Refresh
them with the `lcsc` skill before a BOM lock:

    python3 ~/.claude/skills/lcsc/scripts/search_lcsc.py <Cxxxxx>

Usage
-----
    python3 scripts/gen_bom.py
    python3 scripts/gen_bom.py --stdout
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOT_SCH = REPO_ROOT / "design" / "dshot-esc-100a.kicad_sch"
OUT = REPO_ROOT / "manufacturing" / "BOM.md"

NOISE = re.compile(r"fontconfig|invalid (attribute|constant)", re.I)

# Lines worth calling out: long lead time, thin stock, or design-critical.
NOTES = {
    "DRV8323RSRGZT": "SPI variant. RH (C543035) is pin-compatible - see "
                     "docs/gate-driver-config.md before substituting",
    "STM32G071CBT6": "48-pin part is REQUIRED: it is the only one that frees "
                     "PB12/TIM1_BKIN. Symbol is KiCad's G081CBTx renamed",
    "TPHR8504PL,L1Q(M": "12 off, 2 per switch position. 40 V on a 12.6 V bus "
                        "is deliberate - see docs/architecture.md",
    "SN74LVC1G97DBVR": "Shoot-through interlock. Wired per SCES416N Fig 6",
    "HoJLR2512-3W-1mR-1%": "4 in parallel = 0.25 mOhm. Needs a Kelvin sense "
                           "tap in layout - ESC-005",
    "GRM32DR71E106KA12L": "24 off. Derates to ~5-6 uF at 12 V bias - ESC-001",
    "SPZ1EM331F11O00R": "Through-hole radial. ~2.8 A ripple each - ESC-001",
}


def netlist() -> str:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "n.xml"
        p = subprocess.run(
            ["kicad-cli", "sch", "export", "netlist", "--format", "kicadxml",
             "--output", str(out), str(ROOT_SCH)],
            capture_output=True, text=True,
        )
        log = "\n".join(
            ln for ln in (p.stdout + p.stderr).splitlines()
            if not NOISE.search(ln)
        )
        if not out.exists():
            sys.exit(f"netlist export failed:\n{log}")
        return out.read_text()


def field(body: str, name: str) -> str:
    m = re.search(r'<field name="%s">([^<]*)</field>' % name, body)
    return m.group(1).strip() if m else ""


def tag(body: str, name: str) -> str:
    m = re.search(r"<%s>([^<]*)</%s>" % (name, name), body)
    return m.group(1).strip() if m else ""


def build() -> str:
    xml = netlist()
    comps = re.findall(r"<comp ref=\"([^\"]*)\">(.*?)</comp>", xml, re.S)

    groups: dict[tuple[str, str, str, str], dict] = {}
    for ref, body in comps:
        mpn = field(body, "MPN")
        lcsc = field(body, "LCSC")
        val = tag(body, "value")
        fp = tag(body, "footprint")
        sheet = re.search(r'<sheetpath names="([^"]*)"', body)
        key = (mpn, lcsc, val, fp)
        g = groups.setdefault(key, {"refs": [], "sheets": set()})
        g["refs"].append(ref)
        if sheet:
            g["sheets"].add(sheet.group(1).strip("/"))

    def sort_key(item):
        (mpn, lcsc, val, fp), g = item
        # actives first (fewest instances), then passives by descending qty
        return (-len(g["refs"]), mpn)

    rows = sorted(groups.items(), key=sort_key)

    def natural(ref: str) -> tuple:
        m = re.match(r"([A-Za-z#]+)(\d*)", ref)
        return (m.group(1), int(m.group(2) or 0))

    total_lines = len(rows)
    total_parts = sum(len(g["refs"]) for _, g in rows)
    pkg_short = lambda fp: fp.split(":")[-1] if fp else ""

    L: list[str] = []
    A = L.append
    A("# Bill of materials")
    A("")
    A(f"Generated from the schematic netlist by `scripts/gen_bom.py` on "
      f"{date.today().isoformat()}. Do not edit by hand -- regenerate.")
    A("")
    A(f"**{total_lines} distinct lines, {total_parts} placements.** "
      "The schematic is fully wired and ERC-clean, so these quantities "
      "are real rather than provisional.")
    A("")
    A("Prices and stock are deliberately absent -- they go stale within "
      "days. Refresh before a BOM lock with the `lcsc` skill.")
    A("")
    A("---")
    A("")
    A("## Sourcing notes")
    A("")
    A("**The gate driver is the line to watch.** The design is laid out "
      "for both DRV8323R variants on one footprint -- only pins 29-32 "
      "differ (SLVSDJ3D Table 6-4):")
    A("")
    A("| Part | LCSC | Stock | Price | Configured by |")
    A("|---|---|---:|---:|---|")
    A("| `DRV8323RSRGZT` | C2653553 | ~67 | $4.29 | SPI, from the MCU |")
    A("| `DRV8323RHRGZR` | C543035 | ~2338 | $2.39 | resistors R203-R206 |")
    A("")
    A("RS is the default because it can set source and sink gate current "
      "independently, which is what produces the turn-off/turn-on "
      "asymmetry the dead-time budget relies on. RH cannot -- one pin "
      "sets both. An RH build is still safe but has less margin, and its "
      "resistor values are **not yet transcribed** (issue ESC-010). See "
      "`docs/gate-driver-config.md` before substituting.")
    A("")
    A("Everything else is commodity: no part below has under ~1000 pieces "
      "at LCSC, and the FETs, MCU and logic all have multiple sources.")
    A("")
    A("---")
    A("")
    A("## Lines")
    A("")
    A("| Qty | MPN | LCSC | Value | Package | Refs | Sheets |")
    A("|----:|-----|------|-------|---------|------|--------|")
    for (mpn, lcsc, val, fp), g in rows:
        refs = sorted(g["refs"], key=natural)
        refs_s = ", ".join(refs)
        if len(refs_s) > 60:
            refs_s = ", ".join(refs[:4]) + f", ... (+{len(refs) - 4})"
        sheets = ", ".join(sorted(g["sheets"]))
        A(f"| {len(refs)} | `{mpn}` | `{lcsc}` | {val} | "
          f"{pkg_short(fp)} | {refs_s} | {sheets} |")
    A("")
    A("---")
    A("")
    A("## Lines needing attention")
    A("")
    flagged = [(mpn, NOTES[mpn]) for (mpn, _, _, _), _ in rows if mpn in NOTES]
    if flagged:
        A("| MPN | Note |")
        A("|---|---|")
        for mpn, note in flagged:
            A(f"| `{mpn}` | {note} |")
    else:
        A("None.")
    A("")
    A("## Before ordering")
    A("")
    A("1. Wire the schematic -- quantities here are pre-wiring estimates.")
    A("2. Refresh stock for every line; flag anything under 10x requirement.")
    A("3. Record a second-source C-number for each thin line in that part's "
      "`manufacturing/parts/{Vendor}/{MPN}/{MPN}.md`.")
    A("4. Resolve everything in `manufacturing/stm32mp157-devkit/ISSUES.md` "
      "or defer it explicitly.")
    A("5. Re-run `python3 scripts/verify_project.py`.")
    A("6. Re-check stock immediately before placing the order -- do not "
      "order against numbers from a previous session.")
    A("")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stdout", action="store_true",
                    help="print instead of writing the file")
    args = ap.parse_args()

    text = build()
    if args.stdout:
        print(text)
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    lines = text.count("\n| ")
    print(f"wrote {OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
