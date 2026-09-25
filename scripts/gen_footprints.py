#!/usr/bin/env python3
"""Project-local footprints that KiCad does not ship.

HighCurrentTerminal_8AWG
    The battery and motor terminals carry 100 A continuous. KiCad's
    Connector_Wire library tops out at 2.5 sqmm (~14 AWG, ~25 A) and its
    strain-relief variants are 25 mm long, which makes them unplaceable
    here. This is the land pattern real ESCs use: a large plated hole the
    wire passes through, with a big annular pad on BOTH outer layers so
    the joint is soldered top and bottom.

    8 AWG is 3.26 mm across the conductor, so the hole is 3.6 mm to leave
    room for tinning. The 9 mm pad gives ~50 sqmm of copper per terminal
    for heat spreading into the pour; solder mask is pulled back over the
    whole pad so it can be flooded with solder.

    Resolves ESC-004.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "design" / "lib" / "dshot-esc-100a.pretty"

HOLE = 3.6      # 8 AWG conductor is 3.26 mm
PAD = 9.0       # annular pad diameter, both outer layers
MASK = 9.6      # mask pulled back past the pad edge

TERMINAL = f"""(footprint "HighCurrentTerminal_8AWG"
	(version 20240108)
	(generator "dshot-esc-100a/scripts")
	(generator_version "10.0")
	(layer "F.Cu")
	(descr "High-current wire terminal: {HOLE} mm plated hole for 8 AWG, {PAD} mm pad on both outer layers, mask-free for solder flooding. Rated for 100 A continuous with the wire soldered through. See docs/layout.md.")
	(tags "terminal high-current 8AWG battery motor esc")
	(attr through_hole)
	(property "Reference" "J**"
		(at 0 -6.2 0)
		(layer "F.SilkS")
		(effects (font (size 1 1) (thickness 0.15)))
	)
	(property "Value" "HighCurrentTerminal_8AWG"
		(at 0 6.2 0)
		(layer "F.Fab")
		(effects (font (size 1 1) (thickness 0.15)))
	)
	(fp_circle (center 0 0) (end {PAD/2 + 0.3:.2f} 0)
		(stroke (width 0.12) (type solid)) (fill none) (layer "F.SilkS"))
	(fp_circle (center 0 0) (end {PAD/2:.2f} 0)
		(stroke (width 0.1) (type solid)) (fill none) (layer "F.Fab"))
	(fp_circle (center 0 0) (end {PAD/2 + 0.55:.2f} 0)
		(stroke (width 0.05) (type solid)) (fill none) (layer "F.CrtYd"))
	(pad "1" thru_hole circle
		(at 0 0)
		(size {PAD} {PAD})
		(drill {HOLE})
		(layers "*.Cu" "*.Mask")
		(solder_mask_margin {(MASK - PAD) / 2:.2f})
		(remove_unused_layers no)
		(uuid "a1b2c3d4-0000-4000-8000-000000000001")
	)
)
"""


def main() -> None:
    LIB.mkdir(parents=True, exist_ok=True)
    out = LIB / "HighCurrentTerminal_8AWG.kicad_mod"
    out.write_text(TERMINAL)
    print(f"wrote {out.relative_to(ROOT)}")
    print(f"  {HOLE} mm hole, {PAD} mm pad both outer layers, mask-free")


if __name__ == "__main__":
    main()
