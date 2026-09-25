#!/usr/bin/env python3
"""KiCad-level verification for dshot-esc-100a.

These are checks ERC cannot make, and they exist because of how this
project can fail silently:

  * A malformed ``lib_symbols`` entry produces a file whose parentheses
    balance perfectly but which KiCad refuses to load. The root sheet then
    opens WITHOUT that sheet and reports nothing at all. Only asking KiCad
    to netlist the design and counting per sheet catches it.
  * A multi-unit symbol can lose a whole unit -- all 49 DRV8323R pads must
    appear exactly once, and ERC has no opinion about that.
  * ERC does not open footprint libraries, so a typo'd footprint surfaces
    only at PCB-update time.
  * A clean ERC run is meaningless unless ERC is actually live. Check 5
    proves it by breaking a throwaway copy.

Usage:  python3 scripts/verify_project.py
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "design"
SCH = DESIGN / "dshot-esc-100a.kicad_sch"
STOCK_FP = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")

EXPECT_COMPONENTS = 160
EXPECT_SHEETS = {
    "/Power Input/": 30, "/Gate Driver/": 22, "/Power Stage/": 55,
    "/MCU/": 12, "/Sense/": 17, "/Protection/": 24,
}
# ref -> number of pads that must each appear exactly once
EXPECT_PADS = {"U201": 49, "U401": 48, **{f"Q{n}": 5 for n in range(301, 313)}}

# ERC categories allowed to appear. Deliberately excluded, and they must
# stay that way: endpoint_off_grid (pins off the 2.54 mm grid never snap),
# same_local_global_label (one net labelled both ways is TWO nets and looks
# completely normal on screen), pin_to_pin.
ERC_ALLOWED: set[str] = set()

NOISE = re.compile(r"fontconfig|invalid (attribute|constant)", re.I)


def run(args: list[str]) -> str:
    r = subprocess.run(args, capture_output=True, text=True)
    return "\n".join(l for l in (r.stdout + r.stderr).splitlines()
                     if not NOISE.search(l))


def netlist(sch: Path) -> ET.Element:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "n.xml"
        run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadxml",
             "--output", str(out), str(sch)])
        if not out.exists():
            sys.exit(f"FATAL: kicad-cli could not netlist {sch}")
        return ET.parse(out).getroot()


def main() -> int:
    fails: list[str] = []
    root = netlist(SCH)
    comps = root.findall(".//comp")
    nets = root.findall(".//net")

    # 1 -- every sheet loaded, with the expected population
    print("1. sheets load and are fully populated")
    got = Counter(c.find("sheetpath").get("names") for c in comps)
    for name, n in EXPECT_SHEETS.items():
        have = got.get(name, 0)
        mark = "ok " if have == n else "FAIL"
        print(f"   {mark} {name:<16} {have:>3} / {n}")
        if have != n:
            fails.append(f"sheet {name}: {have} components, expected {n}")
    if len(comps) != EXPECT_COMPONENTS:
        fails.append(f"{len(comps)} components total, expected {EXPECT_COMPONENTS}")
    for extra in set(got) - set(EXPECT_SHEETS):
        fails.append(f"unexpected sheet in netlist: {extra}")

    # 2 -- no component lost its library binding
    print("2. symbol resolution")
    nolib = [c.get("ref") for c in comps
             if c.find("libsource") is None or not c.find("libsource").get("lib")]
    print(f"   {'ok ' if not nolib else 'FAIL'} {len(comps)} components, "
          f"{len(nolib)} with an empty lib")
    fails += [f"{r} has no library binding" for r in nolib]

    # 3 -- multi-pad parts: every pad present exactly once
    print("3. pad integrity")
    pads: dict[str, Counter] = {}
    for net in nets:
        for n in net.findall("node"):
            pads.setdefault(n.get("ref"), Counter())[n.get("pin")] += 1
    for ref, n in sorted(EXPECT_PADS.items()):
        c = pads.get(ref, Counter())
        dup = {k: v for k, v in c.items() if v > 1}
        ok = len(c) == n and not dup
        print(f"   {'ok ' if ok else 'FAIL'} {ref:<6} {len(c):>3} / {n} pads")
        if len(c) != n:
            fails.append(f"{ref}: {len(c)} pads in netlist, expected {n}")
        if dup:
            fails.append(f"{ref}: pads appear more than once: {dup}")

    # 4 -- every footprint string resolves to a real .kicad_mod on disk
    print("4. footprints resolve")
    missing = []
    for c in comps:
        fp = (c.findtext("footprint") or "").strip()
        if not fp:
            missing.append(f"{c.get('ref')} has no footprint")
            continue
        if ":" not in fp:
            missing.append(f"{c.get('ref')} footprint {fp!r} has no library")
            continue
        lib, name = fp.split(":", 1)
        if not (STOCK_FP / f"{lib}.pretty" / f"{name}.kicad_mod").exists():
            missing.append(f"{c.get('ref')}: {fp} not found on disk")
    print(f"   {'ok ' if not missing else 'FAIL'} "
          f"{len(comps) - len(missing)} / {len(comps)} resolve")
    fails += missing[:10]

    # 5 -- ERC is clean AND ERC is actually live
    print("5. ERC")
    with tempfile.TemporaryDirectory() as td:
        rpt = Path(td) / "erc.rpt"
        run(["kicad-cli", "sch", "erc", "--output", str(rpt),
             "--severity-all", str(SCH)])
        text = rpt.read_text() if rpt.exists() else ""
    cats = Counter(re.findall(r"\[([a-z_]+)\]", text))
    bad = {k: v for k, v in cats.items() if k not in ERC_ALLOWED}
    print(f"   {'ok ' if not bad else 'FAIL'} {sum(cats.values())} violations"
          f"{'' if not bad else f': {bad}'}")
    fails += [f"ERC {k} x{v}" for k, v in bad.items()]

    # A clean ERC means nothing unless ERC would have caught a real fault.
    # Break a copy on purpose and confirm it complains.
    with tempfile.TemporaryDirectory() as td:
        copy = Path(td) / "design"
        shutil.copytree(DESIGN, copy)
        p = copy / "02_gate_driver.kicad_sch"
        s = p.read_text()
        i = s.find('(lib_id "power:PWR_FLAG")')
        if i < 0:
            fails.append("self-test: no PWR_FLAG on sheet 02 to remove")
        else:
            start = s.rfind("\t(symbol\n", 0, i)
            depth, j = 0, start
            while True:
                if s[j] == "(":
                    depth += 1
                elif s[j] == ")":
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                j += 1
            p.write_text(s[:start] + s[j:])
            rpt = copy / "erc.rpt"
            run(["kicad-cli", "sch", "erc", "--output", str(rpt),
                 "--severity-all", str(copy / "dshot-esc-100a.kicad_sch")])
            n = len(re.findall(r"\[[a-z_]+\]", rpt.read_text() if rpt.exists() else ""))
            print(f"   {'ok ' if n else 'FAIL'} self-test: removing a PWR_FLAG "
                  f"produced {n} violation(s)")
            if not n:
                fails.append("ERC self-test found nothing -- ERC is NOT live, "
                             "so the clean run above is meaningless")

    print()
    if fails:
        print(f"FAIL -- {len(fails)} problem(s)")
        for f in fails[:25]:
            print(f"  - {f}")
        return 1
    print(f"PASS -- {len(comps)} components, {len(nets)} nets, "
          f"{len(EXPECT_SHEETS)} sheets, ERC clean and proven live")
    return 0


if __name__ == "__main__":
    sys.exit(main())
