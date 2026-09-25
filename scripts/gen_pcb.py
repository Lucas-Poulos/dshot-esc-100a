#!/usr/bin/env python3
"""Floorplan the dshot-esc-100a PCB: stackup, outline, and placement.

Run with KiCad's bundled python (it needs pcbnew):

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/\
Versions/Current/bin/python3 scripts/gen_pcb.py

This EDITS design/dshot-esc-100a.kicad_pcb in place rather than rebuilding
it, so the (path ...) linkage that "Update PCB from Schematic" created is
preserved. Close KiCad first.

------------------------------------------------------------------------
Why the layers are assigned the way they are
------------------------------------------------------------------------
The commutation loop -- bulk ceramic -> high-side FET -> phase node ->
low-side FET -> shunt -> ground -> back to the ceramic -- is the only
loop on this board whose inductance can destroy it. At 150 A with 50 ns
edges, di/dt is 3 A/ns, so every 1 nH costs 3 V of overshoot on a 40 V
FET sitting on a 12.6 V rail.

Loop inductance is set by the distance to the RETURN PLANE, not by how
cleverly the FETs are arranged:

    L = mu0 * d * l / w        d = distance to the return plane

    d = 1.60 mm (return on B.Cu, or high-side and low-side split across
                 the board)                      -> 4.36 nH -> 13.1 V
    d = 0.50 mm (symmetric 4-layer)              -> 1.36 nH ->  4.1 V
    d = 0.20 mm (asymmetric 4-layer, THIS BOARD) -> 0.54 nH ->  1.6 V

So: all twelve FETs on F.Cu, and In1.Cu is an unbroken PGND plane 0.2 mm
beneath them. Splitting high-side and low-side across the board is
intuitively appealing and roughly 8x worse, because it forces the return
current through the full board thickness.

    F.Cu    2 oz   DC+ pour, 12 FETs, phase pours, ceramics, shunt, driver
      ---- 0.20 mm prepreg ----   <- the whole trick is this number
    In1.Cu  1 oz   SOLID PGND. No splits under the bridge, ever.
      ---- 1.065 mm core ----
    In2.Cu  1 oz   gate + sense routing, AGND island under the driver
      ---- 0.20 mm prepreg ----
    B.Cu    2 oz   phase-node lanes down to the motor pads, logic, thermal
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent.parent
PCB = ROOT / "design" / "dshot-esc-100a.kicad_pcb"

# ---- board frame -------------------------------------------------------
BX, BY = 100.0, 60.0          # board origin in KiCad space
W, H = 80.0, 68.0
MOUNT_R = 1.6                 # M3 clearance
MOUNT_INSET = 3.5

# ---- floorplan ---------------------------------------------------------
COL = {"A": 34.0, "B": 50.0, "C": 66.0}   # phase column centres
FET_DX = 3.6                               # half-pitch of a paralleled pair
Y_CERAMIC0 = 3.5      # first of three ceramic rows, 3.5 mm pitch
Y_HS = 16.0           # PQFN courtyard rot90 spans 12.1 - 19.9
Y_HS_GATE = 22.0      # 0603 courtyard 20.3 - 23.7, clear of both
Y_LS = 28.0           # courtyard 24.1 - 31.9
Y_LS_GATE = 33.9      # courtyard 32.2 - 35.6
Y_SHUNT = 38.0        # 2512 courtyard 35.8 - 40.2
Y_DRIVER = 48.0       # VQFN-48 courtyard 43.7 - 52.3
Y_PHASE_PAD = 58.0    # courtyard 52.9 - 63.1

# High-side and low-side FET refs, per phase: (hi_a, hi_b, lo_a, lo_b)
FETS = {"A": (301, 302, 303, 304),
        "B": (305, 306, 307, 308),
        "C": (309, 310, 311, 312)}

TOP, BOT = "top", "bottom"

# Footprints to swap on the board. "Update PCB from Schematic" would do
# this too, but doing it here keeps the script self-contained and means a
# fresh clone reproduces the same board.
SWAP = {ref: ("dshot-esc-100a", "HighCurrentTerminal_8AWG")
        for ref in ("J101", "J102", "J301", "J302", "J303")}
# U201's _ThermalVias variant embeds 0.2 mm vias. This board is 2 oz outer
# copper, where 0.3 mm is the realistic fab minimum, so the plain land
# pattern is used and thermal vias get placed by hand during routing.
SWAP["U201"] = ("Package_DFN_QFN",
                "Texas_RGZ0048A_VQFN-48-1EP_7x7mm_P0.5mm_EP5.15x5.15mm")
STOCK_FP_LIB = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/Package_DFN_QFN.pretty"
PROJ_FP_LIB = str(ROOT / "design" / "lib" / "dshot-esc-100a.pretty")


def mm(v: float) -> int:
    return pcbnew.FromMM(v)


def vec(x: float, y: float):
    return pcbnew.VECTOR2I(mm(BX + x), mm(BY + y))


def build_placement() -> dict[str, tuple[float, float, int, str]]:
    """ref -> (x, y, rotation_deg, side), relative to the board origin.

    Two hard geometric constraints shape this, beyond the loop-inductance
    argument in the module docstring:

    1. Each phase node has to reach its motor terminal on the bottom edge.
       That run happens on B.Cu, in a ~9 mm lane directly below each
       column. Nothing else may live in those lanes, so ALL logic is
       consolidated into x < 30 on B.Cu. (This is not about inductance --
       the motor lead is in series with a ~10-100 uH winding and its own
       inductance is irrelevant. It is about not having to route around
       parts later.)
    2. U201's footprint has plated thermal vias, so B.Cu directly beneath
       the driver is unusable.

    Pitches come from measured pad extents including mask margin:
        0603 2.45x0.95 (2.84 rotated)   0805 2.85x1.40   1210 4.10x2.70
        SOT-23-6 3.60x2.50   SOD-123 4.20x1.20   SMB 6.80x2.30
        2512 7.15x3.35   VQFN-48 7.75 sq   LQFP-48 9.80 sq
        radial D8 body 8.00   terminal pad 9.00 dia
    """
    p: dict[str, tuple[float, float, int, str]] = {}

    # --- battery end (left), all on F.Cu --------------------------------
    p["J101"] = (10.0, 11.0, 0, TOP)         # VBAT+
    p["J102"] = (10.0, 24.0, 0, TOP)        # VBAT-
    p["D101"] = (10.0, 34.0, 90, TOP)       # TVS across the rail
    for i, y in enumerate((9.0, 18.0, 27.0)):
        p[f"C{101 + i}"] = (22.0, y, 90, TOP)      # bulk, 8 mm bodies

    # --- ceramics: three rows spanning the DC+ pour, directly above the
    #     high-side drains. These ARE the commutation loop's source at
    #     high frequency; the electrolytics are far too slow to matter.
    for i in range(24):
        col, row = i % 8, i // 8
        p[f"C{104 + i}"] = (30.0 + col * 4.8, Y_CERAMIC0 + row * 3.5, 0, TOP)

    # --- the bridge ------------------------------------------------------
    for ph, xc in COL.items():
        hi_a, hi_b, lo_a, lo_b = FETS[ph]
        i = "ABC".index(ph)
        # Rotation 90 puts the source/gate edge at the BOTTOM of the part
        # and leaves the big centre drain pad facing the pour above it, so
        # current flows straight down the column:
        #     DC+ -> HS drain -> HS source -> phase -> LS drain
        #         -> LS source -> shunt -> PGND
        # Rotating the other way (270) makes every phase current double
        # back on itself and doubles the loop area.
        for k, ref in enumerate((hi_a, hi_b)):
            p[f"Q{ref}"] = (xc + (k * 2 - 1) * FET_DX, Y_HS, 90, TOP)
        for k, ref in enumerate((lo_a, lo_b)):
            p[f"Q{ref}"] = (xc + (k * 2 - 1) * FET_DX, Y_LS, 90, TOP)
        for k in range(2):
            fx = xc + (k * 2 - 1) * FET_DX
            p[f"R{301 + i * 4 + k}"] = (fx - 1.6, Y_HS_GATE, 90, TOP)
            p[f"R{313 + i * 4 + k}"] = (fx + 1.6, Y_HS_GATE, 90, TOP)
            p[f"R{303 + i * 4 + k}"] = (fx - 1.6, Y_LS_GATE, 90, TOP)
            p[f"R{315 + i * 4 + k}"] = (fx + 1.6, Y_LS_GATE, 90, TOP)
        p[f"J{301 + i}"] = (xc, Y_PHASE_PAD, 0, TOP)   # motor terminal

    # --- shunt: 4x 1 mOhm 2512 under the common low-side source ---------
    for i in range(4):
        p[f"RS{301 + i}"] = (38.0 + i * 8.0, Y_SHUNT, 0, TOP)

    # --- gate driver, in the gap between the phase-A and phase-B lanes --
    p["U201"] = (42.0, Y_DRIVER, 0, TOP)
    # One row between the shunt (courtyard ends 40.2) and the driver
    # (starts 43.7). Sitting over a phase lane is fine -- the lanes are on
    # B.Cu; what matters is staying clear of the THT terminal pads.
    for i, ref in enumerate(("C201", "C202", "C203", "C204",
                             "C205", "C206", "C207", "C208")):
        p[ref] = (31.0 + i * 4.2, 42.0, 0, TOP)
    p["L201"] = (58.0, 48.0, 0, TOP)
    p["D201"] = (58.0, 55.0, 0, TOP)
    for i in range(3):                       # common gate R + turn-off diode
        x = 22.0 + (i % 2) * 5.0
        y = 40.0 + (i // 2) * 0.0 + i * 3.2
        p[f"R{325 + i * 2}"] = (21.0, 42.0 + i * 3.4, 0, TOP)
        p[f"D{301 + i * 2}"] = (26.5, 42.0 + i * 3.4, 0, TOP)
        p[f"R{326 + i * 2}"] = (21.0, 53.5 + i * 3.4, 0, TOP)
        p[f"D{302 + i * 2}"] = (26.5, 53.5 + i * 3.4, 0, TOP)
    for i in range(11):                      # driver config / feedback
        p[f"R{201 + i}"] = (70.0 + (i % 3) * 3.6, 38.0 + (i // 3) * 3.0, 0, TOP)

    # --- sense: BEMF dividers hug their own phase column, on B.Cu -------
    for i, ph in enumerate("ABC"):
        p[f"R{501 + i}"] = (COL[ph] - 6.4, 22.0, 90, BOT)
        p[f"R{504 + i}"] = (COL[ph] - 6.4, 26.5, 90, BOT)
        p[f"R{507 + i}"] = (COL[ph] + 6.4, 22.0, 90, BOT)
    p["R510"] = (COL["B"] + 6.4, 26.5, 90, BOT)
    for i, ref in enumerate(("R511", "R512", "C501", "R513", "R514", "C502")):
        p[ref] = (40.0 + (i % 2) * 3.2, 56.0 + (i // 2) * 3.0, 0, BOT)
    p["C503"] = (40.0, 65.0, 0, BOT)

    # --- ALL logic on B.Cu at x < 30, clear of every phase lane ---------
    # The three bulk electrolytics are through-hole, so their pads block
    # B.Cu at x 16-24, y 5-33. Everything here sits below that.
    for i in range(6):                       # interlock gates + decoupling
        x = 5.0 + (i % 3) * 9.0
        y = 35.0 + (i // 3) * 5.0
        p[f"U{601 + i}"] = (x, y, 0, BOT)
        p[f"C{601 + i}"] = (x + 4.5, y, 0, BOT)
    for i in range(12):                      # interlock pulldowns
        p[f"R{601 + i}"] = (4.0 + (i % 6) * 4.0, 44.0 + (i // 6) * 3.0, 0, BOT)

    p["U401"] = (10.0, 55.0, 0, BOT)
    for i, ref in enumerate(("C401", "C402", "C403")):
        p[ref] = (19.0, 51.5 + i * 3.0, 0, BOT)
    for i, ref in enumerate(("C404", "C405", "C406")):
        p[ref] = (23.5, 51.5 + i * 3.0, 0, BOT)
    p["R401"] = (27.2, 51.5, 0, BOT)
    p["R402"] = (27.2, 54.5, 0, BOT)
    p["D401"] = (27.2, 57.5, 0, BOT)
    # Headers on the bottom edge of the logic block. Everywhere else on
    # B.Cu is either a phase lane, a 9 mm THT terminal pad, or sits under
    # an F.Cu power part (these are through-hole, so they clash with both
    # sides).
    p["J401"] = (11.7, 64.0, 90, BOT)         # SWD, 2x05 1.27
    p["J402"] = (23.5, 64.0, 90, BOT)        # signal / telemetry

    return p


def terminal_nets() -> dict[tuple[str, str], str]:
    """Expected net per terminal, read from the schematic -- not hardcoded."""
    import tempfile
    import xml.etree.ElementTree as ET
    out = tempfile.mktemp(suffix=".xml")
    subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format",
                    "kicadxml", "--output", out,
                    str(ROOT / "design" / "dshot-esc-100a.kicad_sch")],
                   capture_output=True)
    # Keyed by (ref, pad) -- NOT by ref. U201 is a 49-pad part; mapping
    # one net per reference and applying it to every pad would short the
    # entire gate driver together.
    want: dict[tuple[str, str], str] = {}
    for net in ET.parse(out).getroot().findall(".//net"):
        name = net.get("name")
        for n in net.findall("node"):
            if n.get("ref") in SWAP:
                want[(n.get("ref"), n.get("pin"))] = name
    Path(out).unlink(missing_ok=True)
    return want


def _net(board, name: str):
    """Look up a net by name, creating it if the board has lost it."""
    net = board.FindNet(name)
    if net is None:
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
    return net


def swap_terminals() -> int:
    """Pass 1: replace the placeholder wire pads. Runs on its own freshly
    loaded board and saves immediately.

    This is a separate pass because pcbnew's SWIG type registry is
    clobbered by board.Remove(): afterwards FootprintLoad() returns bare
    SwigPyObjects and even previously-loaded footprints lose .Pads().
    Doing the swap first, on an untouched board, sidesteps all of it.
    """
    board = pcbnew.LoadBoard(str(PCB))
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    want = terminal_nets()
    swapped = 0
    for ref, (lib, name) in SWAP.items():
        old = fps.get(ref)
        if old is None or str(old.GetFPIDAsString()).split(":")[-1] == name:
            continue
        libdir = PROJ_FP_LIB if lib == "dshot-esc-100a" else STOCK_FP_LIB
        new = pcbnew.FootprintLoad(libdir, name)
        if new is None:
            sys.exit(f"FATAL: cannot load {lib}:{name}")
        new.SetReference(ref)
        new.SetValue(old.GetValue())
        new.SetPath(old.GetPath())              # keep the schematic linkage
        new.SetPosition(old.GetPosition())
        # Copy nets PER PAD NUMBER. U201 is a 49-pad part; taking the
        # first pad's net and applying it to all of them shorts the whole
        # gate driver together.
        old_nets = {op.GetNumber(): op.GetNetname() for op in old.Pads()}
        board.Remove(old)
        board.Add(new)
        for np_ in new.Pads():
            nn = want.get((ref, np_.GetNumber())) or old_nets.get(np_.GetNumber())
            if nn:
                np_.SetNet(_net(board, nn))
        swapped += 1
    # Always repair nets, even when nothing was swapped this run: an
    # earlier pass could have replaced the footprint without carrying the
    # net across, and an unnetted 100 A terminal is invisible until DRC.
    fixed = 0
    for (ref, padnum), netname in want.items():
        fp = fps.get(ref)
        if fp is None:
            continue
        for pad in fp.Pads():
            if pad.GetNumber() == padnum and pad.GetNetname() != netname:
                pad.SetNet(_net(board, netname))
                fixed += 1

    if swapped or fixed:
        pcbnew.SaveBoard(str(PCB), board)
    print(f"SWAPPED {swapped}")
    print(f"NETFIXED {fixed}")
    return swapped


STACKUP = """	(stackup
			(layer "F.SilkS" (type "Top Silk Screen"))
			(layer "F.Paste" (type "Top Solder Paste"))
			(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
			(layer "F.Cu" (type "copper") (thickness 0.07))
			(layer "dielectric 1" (type "prepreg") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In1.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 2" (type "core") (thickness 0.97) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In2.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 3" (type "prepreg") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "B.Cu" (type "copper") (thickness 0.07))
			(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
			(layer "B.Paste" (type "Bottom Solder Paste"))
			(layer "B.SilkS" (type "Bottom Silk Screen"))
			(copper_finish "ENIG")
			(dielectric_constraints no)
		)
"""


def _zone(net_code: int, net_name: str, layer: str, x1, y1, x2, y2,
          uid_suffix: str) -> str:
    """A filled-polygon zone covering a rectangle, emitted as text.

    pcbnew's ZONE/SHAPE_POLY_SET bindings are awkward and the SWIG state
    is already fragile after the placement pass, so zones go in as
    s-expressions where the result is exactly predictable.
    """
    return f'''	(zone
		(net {net_code})
		(net_name "{net_name}")
		(layer "{layer}")
		(uuid "b0000000-0000-4000-8000-0000000{uid_suffix}")
		(hatch edge 0.5)
		(connect_pads (clearance 0.25))
		(min_thickness 0.25)
		(filled_areas_thickness no)
		(fill
			(thermal_gap 0.3)
			(thermal_bridge_width 0.6)
			(island_removal_mode 1)
			(island_area_min 10)
		)
		(polygon
			(pts
				(xy {x1} {y1}) (xy {x2} {y1}) (xy {x2} {y2}) (xy {x1} {y2})
			)
		)
	)
'''


def apply_stackup_and_planes() -> None:
    """Write the stackup and the two planes that define the loop.

    The 0.20 mm F.Cu -> In1.Cu prepreg is the single most important number
    on this board: it sets the commutation-loop inductance at 0.54 nH.
    A stock symmetric 4-layer stackup (0.5 mm) would give 1.36 nH, and a
    return on B.Cu 4.36 nH. Tell the fab this is NOT negotiable.
    """
    t = PCB.read_text()

    # In1.Cu is a plane, not a signal layer.
    t = t.replace('(4 "In1.Cu" signal)', '(4 "In1.Cu" power "PGND")')

    if "(stackup" not in t:
        t = t.replace("\t(setup\n", "\t(setup\n" + STACKUP, 1)

    # Remove ALL existing zones before re-adding. Deduping by UUID does
    # not work -- pcbnew.SaveBoard() rewrites every UUID on save, so each
    # run's pours looked new and they stacked up (14 zones, 42 DRC
    # intersect errors). Every zone on this board is generated here, so
    # clearing them is safe. Revisit if pours are ever drawn by hand.
    while "\t(zone" in t:
        start = t.index("\t(zone")
        depth, j, instr = 0, start, False
        while True:
            c = t[j]
            if instr:
                instr = not (c == '"' and t[j - 1] != "\\")
            elif c == '"':
                instr = True
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        t = t[:start] + t[j:].lstrip("\n")

    if True:
        # net codes are resolved by name at load; 0 is the safe placeholder
        # KiCad re-resolves from net_name.
        import re as _re
        def netcode(name):
            m = _re.search(rf'\(net (\d+) "{_re.escape(name)}"\)', t)
            return int(m.group(1)) if m else 0
        gnd, batt = netcode("GND"), netcode("+BATT")
        zones = (
            # In1.Cu: unbroken PGND over the whole board. This is the
            # return path for every commutation loop. Never split it.
            _zone(gnd, "GND", "In1.Cu", BX + 0.6, BY + 0.6,
                  BX + W - 0.6, BY + H - 0.6, "001")
            # F.Cu: DC+ over the ceramic rows and the high-side drains.
            + _zone(batt, "+BATT", "F.Cu", BX + 27.0, BY + 1.5,
                    BX + W - 2.0, BY + 12.6, "002")
        )
        t = t.rstrip()
        assert t.endswith(")")
        t = t[:-1] + zones + ")\n"

    PCB.write_text(t)
    print("stackup: F.Cu 2oz | 0.20 prepreg | In1 PGND | 0.97 core | "
          "In2 | 0.20 prepreg | B.Cu 2oz  = 1.60 mm")
    print("planes: In1.Cu = solid PGND, F.Cu = +BATT over the bridge")


def main() -> int:
    if not PCB.exists():
        sys.exit(f"FATAL: {PCB} not found")

    # pcbnew tolerates exactly ONE LoadBoard per process -- a second call
    # returns a bare SwigPyObject. So pass 1 runs in its own interpreter.
    r = subprocess.run([sys.executable, __file__, "--swap"],
                       capture_output=True, text=True)
    swapped = 0
    netfixed = 0
    for line in r.stdout.splitlines():
        if line.startswith("SWAPPED "):
            swapped = int(line.split()[1])
        if line.startswith("NETFIXED "):
            netfixed = int(line.split()[1])
    if r.returncode != 0:
        sys.exit(f"FATAL: terminal swap pass failed:\n{r.stdout}\n{r.stderr}")

    board = pcbnew.LoadBoard(str(PCB))

    # Collect footprints FIRST. board.Remove() on a drawing invalidates
    # pcbnew's iterators, after which GetFootprints() yields raw
    # SwigPyObjects with no methods -- a confusing failure that only
    # shows up on the second run, once there is something to remove.
    fps = {f.GetReference(): f for f in board.GetFootprints()}

    # Load replacement footprints NOW, before anything mutates the board.
    # pcbnew's plugin handle is invalidated by board.Remove(), after which
    # FootprintLoad() fails with a bare-SwigPyObject AttributeError.
    # ---- 4 copper layers -------------------------------------------------
    board.SetCopperLayerCount(4)

    # ---- board outline + mounting holes ---------------------------------
    for d in list(board.GetDrawings()):
        if d.GetLayer() == pcbnew.Edge_Cuts:
            board.Remove(d)
    corners = [(0, 0), (W, 0), (W, H), (0, H)]
    for i in range(4):
        seg = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(vec(*corners[i]))
        seg.SetEnd(vec(*corners[(i + 1) % 4]))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(mm(0.1))
        board.Add(seg)
    for cx, cy in ((MOUNT_INSET, MOUNT_INSET), (W - MOUNT_INSET, MOUNT_INSET),
                   (MOUNT_INSET, H - MOUNT_INSET),
                   (W - MOUNT_INSET, H - MOUNT_INSET)):
        c = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_CIRCLE)
        c.SetCenter(vec(cx, cy))
        c.SetEnd(vec(cx + MOUNT_R, cy))
        c.SetLayer(pcbnew.Edge_Cuts)
        c.SetWidth(mm(0.1))
        board.Add(c)

    # ---- placement -------------------------------------------------------
    plan = build_placement()
    missing = sorted(set(fps) - set(plan))
    unknown = sorted(set(plan) - set(fps))
    for ref, (x, y, rot, side) in plan.items():
        fp = fps.get(ref)
        if fp is None:
            continue
        want_bottom = side == BOT
        if fp.IsFlipped() != want_bottom:
            fp.Flip(fp.GetPosition(), False)
        fp.SetPosition(vec(x, y))
        fp.SetOrientationDegrees(rot)

    pcbnew.SaveBoard(str(PCB), board)
    apply_stackup_and_planes()

    placed = len(plan) - len(unknown)
    print(f"4 copper layers, {W:.0f} x {H:.0f} mm outline, 4 mounting holes")
    print(f"placed {placed} / {len(fps)} footprints"
          + (f", swapped {swapped} terminals" if swapped else "")
          + (f", repaired {netfixed} terminal net(s)" if netfixed else ""))
    top = sum(1 for r, v in plan.items() if v[3] == TOP and r in fps)
    print(f"  F.Cu {top}   B.Cu {placed - top}")
    if missing:
        print(f"  NOT IN PLAN ({len(missing)}): {', '.join(missing[:20])}")
    if unknown:
        print(f"  in plan but not on board ({len(unknown)}): {unknown[:10]}")
    return 1 if (missing or unknown) else 0


if __name__ == "__main__":
    if "--swap" in sys.argv:
        swap_terminals()
        sys.exit(0)
    sys.exit(main())
