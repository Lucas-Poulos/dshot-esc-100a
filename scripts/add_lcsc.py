#!/usr/bin/env python3
"""
add_lcsc.py — Inject LCSC part number properties into KiCad schematic files.

Inserts a hidden (property "LCSC" "Cxxxxxx") into each KiCad symbol block,
identified by UUID. Skips symbols that already have an LCSC property.

Usage
-----
1. Build UUID_LCSC: a dict mapping each component's KiCad UUID to its LCSC
   C-number. UUIDs are in the .kicad_sch file next to each (symbol ...) block.

2. Set BASE to the directory containing your .kicad_sch files.

3. Run: python3 scripts/add_lcsc.py

The script modifies files in-place. Run only when KiCad is closed:
    pgrep -fil kicad   # must return nothing

Finding UUIDs
-------------
    grep -n 'uuid' design/MySheet.kicad_sch | head -40
Or open the .kicad_sch in a text editor and search for the component
reference or value — the UUID is in the same symbol block.
"""

import os

# ── Configuration ──────────────────────────────────────────────────────────────

BASE = "design"   # directory containing .kicad_sch files

SHEETS = [
    # List your schematic sheets here, e.g.:
    # "TopLevel.kicad_sch",
    # "MCU.kicad_sch",
]

# Map: KiCad symbol UUID → LCSC C-number
UUID_LCSC = {
    # Example:
    # "0e0b13ef-7b19-4328-8622-ac7468502a9f": "C15742",   # STM32F405RGT6
    # "c57bb584-5b85-4e68-a18e-c2fda052dfd2": "C133937",  # ferrite bead
}

# ── Property template (KiCad 6+ format) ───────────────────────────────────────

LCSC_PROP = (
    '\t\t(property "LCSC" "{lcsc}"\n'
    '\t\t\t(at 0 0 0)\n'
    '\t\t\t(effects\n'
    '\t\t\t\t(font\n'
    '\t\t\t\t\t(size 1.27 1.27)\n'
    '\t\t\t\t)\n'
    '\t\t\t\t(hide yes)\n'
    '\t\t\t)\n'
    '\t\t)\n'
)

# ── Core logic ─────────────────────────────────────────────────────────────────

def add_lcsc_to_file(path, uuid_lcsc):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    original = text
    added = []
    skipped_existing = []
    not_found = []

    for uuid_str, lcsc in uuid_lcsc.items():
        if uuid_str not in text:
            not_found.append(uuid_str)
            continue

        uuid_pos = text.index(uuid_str)
        sym_start = text.rfind('\t(symbol\n', 0, uuid_pos)
        if sym_start == -1:
            not_found.append(f"no-sym-start:{uuid_str}")
            continue

        depth = 0
        j = sym_start + 1
        sym_end = -1
        while j < len(text):
            if text[j] == '(':
                depth += 1
            elif text[j] == ')':
                depth -= 1
                if depth == 0:
                    sym_end = j + 1
                    break
            j += 1

        if sym_end == -1:
            not_found.append(f"no-sym-end:{uuid_str}")
            continue

        block = text[sym_start:sym_end]
        if '"LCSC"' in block:
            skipped_existing.append(uuid_str)
            continue

        if text[sym_end - 2:sym_end] == '\t)':
            insert_pos = sym_end - 2
        else:
            insert_pos = text.rfind('\n\t)', sym_start, sym_end)
            if insert_pos == -1:
                not_found.append(f"no-insert-pos:{uuid_str}")
                continue
            insert_pos += 1

        prop = LCSC_PROP.format(lcsc=lcsc)
        text = text[:insert_pos] + prop + text[insert_pos:]
        added.append((uuid_str, lcsc))

    if text != original:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    return added, skipped_existing, not_found


def main():
    total_added = 0
    total_skipped = 0

    for sheet in SHEETS:
        path = os.path.join(BASE, sheet)
        if not os.path.exists(path):
            print(f"SKIP (not found): {sheet}")
            continue

        added, skipped, not_found = add_lcsc_to_file(path, UUID_LCSC)
        errors = [u for u in not_found if u.startswith("no-")]

        print(f"{sheet}:")
        print(f"  Added:   {len(added)}")
        print(f"  Already: {len(skipped)}")
        if errors:
            print(f"  Errors:  {len(errors)}")
            for e in errors:
                print(f"    {e}")
        for uuid_str, lcsc in added:
            print(f"  + {uuid_str[:8]}... → {lcsc}")
        print()

        total_added += len(added)
        total_skipped += len(skipped)

    print(f"Total added: {total_added}, already had LCSC: {total_skipped}")


if __name__ == "__main__":
    main()
