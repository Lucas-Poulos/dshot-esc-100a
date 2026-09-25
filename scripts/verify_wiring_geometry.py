#!/usr/bin/env python3
"""Prove the pin-placement transform against KiCad, rather than trusting it.

``Wirer`` turns a pin reference like ``("U101", "PGND1")`` into an absolute
millimetre coordinate, by reading the pin out of the symbol library and
applying the component's rotation and mirroring. Every net on this board
depends on that arithmetic being right, and a transform that is wrong only
for, say, ``rot=270 mirror=y`` produces a schematic that looks perfectly
sensible and is silently miswired.

Text-level checks cannot catch that. So this builds a throwaway project
with a component at **every rotation and mirror combination**, labels each
pin with a net name that encodes where it should land, exports the netlist
through ``kicad-cli``, and asserts the pin actually arrived on that net.

    python3 scripts/verify_wiring_geometry.py

Run it after touching ``_xform``, ``_outward``, ``SymbolCache.pins`` or any
of the ``Wirer`` geometry.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kicad_sch import (  # noqa: E402
    Comp, Note, Sheet, SymbolCache, Wirer, uid,
    write_lib_tables, write_project, write_root, write_sheet,
)

PROJECT = "geomtest"
ROOT_UUID = uid("root/" + PROJECT)
NOISE = re.compile(r"fontconfig|invalid (attribute|constant)", re.I)

# Two-pin passives sit symmetrically about the origin, so a sign error in
# the transform swaps their pins and is caught. The 4-way connector adds
# pins that are *not* symmetric -- they run down one side -- which catches a
# rotation that is right about the axis but backwards along it.
#
# Every pin used here must be at its own coordinate. A symbol like
# ``Device:Crystal_GND24``, whose pins 2 and 4 are one node, would merge two
# labels into one net and look like a transform failure when it is not.
CASES = [
    ("Device:R", ["1", "2"]),
    ("Device:C", ["1", "2"]),
    ("Connector_Generic:Conn_01x04", ["1", "2", "3", "4"]),
    # Keeps all of its pins in unit 0, the "common to every unit" unit.
    # Collecting only unit 1 finds no pins at all here.
    ("Switch:SW_Push", ["1", "2"]),
]
ROTS = [0, 90, 180, 270]
MIRRORS = [None, "x", "y"]


def build(tmp: Path) -> list[tuple[str, str, str]]:
    """Lay out the matrix and return the (ref, pin, expected net) triples."""
    comps: list[Comp] = []
    expect: list[tuple[str, str, str]] = []
    idx = 0
    x, y = 40.0, 40.0
    for lib_id, pin_nums in CASES:
        for rot in ROTS:
            for mirror in MIRRORS:
                idx += 1
                ref = f"X{idx}"
                comps.append(Comp(ref, lib_id, "T", x, y, rot=rot,
                                  mirror=mirror))
                for pn in pin_nums:
                    expect.append((ref, pn, f"N_{ref}_{pn}"))
                x += 40
                if x > 400:
                    x, y = 40.0, y + 40

    sheet = Sheet("geom.kicad_sch", "Geom", "2", "A2", "Geometry", comps,
                  [Note("pin transform matrix", 20, 18, 3.0, True)])
    cache = SymbolCache({})
    w = Wirer(sheet, cache)
    for ref, pn, net in expect:
        w.label(ref, pn, net, kind="global")

    design = tmp / "design"
    design.mkdir(parents=True)
    write_sheet(design / sheet.filename, sheet, cache, PROJECT, ROOT_UUID,
                "T", "T")
    write_root(design / f"{PROJECT}.kicad_sch", [sheet], PROJECT, ROOT_UUID,
               "Geometry", "T", "T", [], [])
    write_project(design / f"{PROJECT}.kicad_pro", PROJECT, [sheet],
                  ROOT_UUID)
    write_lib_tables(design, [], [])
    if cache.missing:
        raise SystemExit(f"symbols missing: {cache.missing}")
    return expect


def netlist(design: Path) -> dict[str, set[tuple[str, str]]]:
    out = design / "net.xml"
    r = subprocess.run(
        ["kicad-cli", "sch", "export", "netlist", "--format", "kicadxml",
         "--output", str(out), str(design / f"{PROJECT}.kicad_sch")],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        msg = "\n".join(l for l in r.stderr.splitlines() if not NOISE.search(l))
        raise SystemExit(f"kicad-cli failed:\n{msg}")
    nets: dict[str, set[tuple[str, str]]] = {}
    for m in re.finditer(
            r'<net code="\d+" name="([^"]*)"[^>]*>(.*?)</net>',
            out.read_text(), re.S):
        nets[m.group(1)] = {
            (n.group(1), n.group(2))
            for n in re.finditer(r'<node ref="([^"]*)" pin="([^"]*)"',
                                 m.group(2))
        }
    return nets


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        expect = build(tmp)
        nets = netlist(tmp / "design")

    bad = []
    for ref, pn, want in expect:
        got = nets.get(want, set())
        if got != {(ref, pn)}:
            bad.append((want, f"{ref}.{pn}", sorted(got) or "net absent"))

    total = len(expect)
    print(f"pin transform: {total} pins across "
          f"{len(CASES)} symbols x {len(ROTS)} rotations x "
          f"{len(MIRRORS)} mirror states")
    if bad:
        print(f"  FAIL  {len(bad)} of {total} landed on the wrong net")
        for want, pin, got in bad[:15]:
            print(f"        {pin:<10} expected net {want:<16} got {got}")
        return 1
    print(f"  ok    all {total} pins landed on their own net")
    print("\nPASS  pin coordinates, stub direction and mirroring agree "
          "with KiCad")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
