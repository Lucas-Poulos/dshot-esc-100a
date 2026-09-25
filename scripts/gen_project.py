#!/usr/bin/env python3
"""Generate the whole dshot-esc-100a KiCad project into design/.

Everything in design/ is produced here -- project file, root sheet, six
sub-sheets, placement, and (via wire_sheets.py) connectivity. Hand-editing
a .kicad_sch and then re-running this silently destroys the edit. See
CLAUDE.md.

Part numbers: every LCSC code below was resolved with
    python3 ~/.claude/skills/lcsc/scripts/search_lcsc.py <MPN>
None are guessed. Anything unresolved is the literal string "TBD" with a
matching entry in manufacturing/dshot-esc-100a/ISSUES.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

from kicad_sch import (
    Comp, Note, Sheet, SymbolCache, uid,
    write_sheet, write_root, write_project, write_lib_tables,
)
import wire_sheets

REPO_ROOT = Path(__file__).resolve().parent.parent
DESIGN = REPO_ROOT / "design"
PROJECT = "dshot-esc-100a"
PROJ_LIB = "dshot-esc-100a"
REV = "A.1"
COMPANY = "Lucas Poulos"
ROOT_UUID = uid("root/" + PROJECT)

DS = {
    "drv": "https://www.ti.com/lit/ds/symlink/drv8323.pdf",
    "stm": "https://www.st.com/resource/en/datasheet/stm32g071cb.pdf",
    "fet": "https://toshiba.semicon-storage.com/info/TPHR8504PL_datasheet_en.pdf",
    "1g97": "https://www.ti.com/lit/ds/symlink/sn74lvc1g97.pdf",
}

# ==========================================================================
# Parts catalogue
#   PASSIVES: key -> (lib_id, value, footprint, MPN, LCSC)
# ==========================================================================
R0603 = "Resistor_SMD:R_0603_1608Metric"
R0805 = "Resistor_SMD:R_0805_2012Metric"
R2512 = "Resistor_SMD:R_2512_6332Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
C1210 = "Capacitor_SMD:C_1210_3225Metric"

PASSIVES: dict[str, tuple[str, str, str, str, str]] = {
    # --- resistors ---
    "R_4R7":   ("Device:R", "4.7",   R0805, "FRC0805F4R70TS",  "C2933459"),
    "R_10K":   ("Device:R", "10k",   R0603, "FRC0603F1002TS",  "C2906982"),
    "R_1K":    ("Device:R", "1k",    R0603, "FRC0603F1001TS",  "C2907002"),
    "R_100K":  ("Device:R", "100k",  R0603, "0603WAF1003T5E",  "C25803"),
    "R_33K2":  ("Device:R", "33.2k", R0603, "FRC0603F3322TS",  "C2933200"),
    "R_0R":    ("Device:R", "0",     R0603, "RCA030RLF",       "C22356631"),
    "R_SHUNT": ("Device:R", "1m",    R2512, "HoJLR2512-3W-1mR-1%", "C2903470"),
    # --- capacitors ---
    "C_100N":  ("Device:C", "100n",  C0603, "CC0603KRX7R9BB104", "C14663"),
    "C_47N":   ("Device:C", "47n",   C0603, "CL10B473KB8NNNC",   "C1622"),
    "C_1U":    ("Device:C", "1u",    C0603, "CL10B105KA8NNNC",   "C29936"),
    "C_4U7":   ("Device:C", "4.7u",  C0805, "CL21B475KAFNNNE",   "C98195"),
    "C_10U":   ("Device:C", "10u",   C1210, "GRM32DR71E106KA12L", "C77100"),
    "C_330U":  ("Device:C_Polarized", "330u/25V", "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm",
                "SPZ1EM331F11O00R", "C160677"),
    # --- discretes ---
    "D_SCH":   ("Device:D_Schottky", "B5819W", "Diode_SMD:D_SOD-123",
                "B5819W SL", "C8598"),
    "D_TVS":   ("Device:D_TVS", "SMBJ20A", "Diode_SMD:D_SMB",
                "SMBJ20A", "C364296"),
    "LED_G":   ("Device:LED", "green", "LED_SMD:LED_0603_1608Metric",
                "XL-1608UGC-04", "C965804"),
    "L_33U":   ("Device:L", "33u", "Inductor_SMD:L_7.3x7.3_H3.5",
                "SLS6D38S330MTT", "C364136"),
    "NTC_10K": ("Device:Thermistor_NTC", "10k NTC", R0603,
                "NCP18XH103F03RB", "C13564"),
}

# ACTIVES: key -> (lib_id, value, footprint, MPN, LCSC, datasheet key)
FP_DRV = ("Package_DFN_QFN:Texas_RGZ0048A_VQFN-48-1EP_7x7mm_P0.5mm"
          "_EP5.15x5.15mm_ThermalVias")
FP_FET = "Package_DFN_QFN:PQFN-8-EP_6x5mm_P1.27mm_Generic"
FP_WIRE = "Connector_Wire:SolderWire-2.5sqmm_1x01_D2.4mm_OD3.6mm_Relief"

ACTIVES: dict[str, tuple[str, str, str, str, str, str]] = {
    "DRV":  (f"{PROJ_LIB}:DRV8323R", "DRV8323RS", FP_DRV,
             "DRV8323RSRGZT", "C2653553", "drv"),
    "MCU":  (f"{PROJ_LIB}:STM32G071CBTx", "STM32G071CBT6",
             "Package_QFP:LQFP-48_7x7mm_P0.5mm", "STM32G071CBT6",
             "C432212", "stm"),
    "FET":  ("Transistor_FET:Q_NMOS_SSSGD_AvalancheRated", "TPHR8504PL", FP_FET,
             "TPHR8504PL,L1Q(M", "C5331611", "fet"),
    "1G97": ("74xGxx:74LVC1G97", "SN74LVC1G97",
             "Package_TO_SOT_SMD:SOT-23-6", "SN74LVC1G97DBVR", "C128411", "1g97"),
    "TERM": ("Connector:Conn_01x01_Pin", "TERM", FP_WIRE, "-", "-", ""),
    "SWD":  ("Connector_Generic:Conn_02x05_Odd_Even", "SWD",
             "Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical",
             "-", "-", ""),
    "SIG":  ("Connector_Generic:Conn_01x04", "SIGNAL",
             "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
             "-", "-", ""),
}


def _lookup(key: str) -> tuple[str, str, str, str, str, str]:
    if key in ACTIVES:
        return ACTIVES[key]
    if key in PASSIVES:
        lib_id, val, fp, mpn, lcsc = PASSIVES[key]
        return lib_id, val, fp, mpn, lcsc, ""
    raise KeyError(f"part {key!r} is in neither ACTIVES nor PASSIVES")


def act(ref, key, x, y, unit=1, value=None, extra=None) -> Comp:
    lib_id, val, fp, mpn, lcsc, dskey = _lookup(key)
    props = {"Footprint": fp, "Datasheet": DS.get(dskey, ""),
             "MPN": mpn, "LCSC": lcsc}
    if extra:
        props.update(extra)
    return Comp(ref, lib_id, value or val, x, y, unit=unit, props=props)


def psv(ref, key, x, y, rot=0, value=None) -> Comp:
    lib_id, val, fp, mpn, lcsc, dskey = _lookup(key)
    return Comp(ref, lib_id, value or val, x, y, rot=rot,
                props={"Footprint": fp, "Datasheet": DS.get(dskey, ""),
                       "MPN": mpn, "LCSC": lcsc})


def row(prefix, start, key, n, x, y, dx=12.7, per_row=10, dy=20.32,
        rot=0, value=None) -> list[Comp]:
    out = []
    for i in range(n):
        out.append(psv(f"{prefix}{start + i}", key,
                       x + (i % per_row) * dx, y + (i // per_row) * dy,
                       rot=rot, value=value))
    return out


# ==========================================================================
# Sheets
# ==========================================================================

# Phase letter -> (high-side FET refs, low-side FET refs)
PHASES = ("A", "B", "C")


def sheet_01_power() -> Sheet:
    """Battery input, transient clamp, bulk energy store."""
    c: list[Comp] = [
        act("J101", "TERM", 40, 60, value="VBAT+"),
        act("J102", "TERM", 40, 90, value="VBAT-"),
        psv("D101", "D_TVS", 70, 75, rot=0),
        psv("C101", "C_330U", 100, 75),
        psv("C102", "C_330U", 120, 75),
        psv("C103", "C_330U", 140, 75),
    ]
    # 24x 10uF 1210 distributed across the bridge (see power-budget.md).
    c += row("C", 104, "C_10U", 24, 180, 60, dx=15.24, per_row=8, dy=30.48)
    notes = [
        Note("01  POWER INPUT + BULK", 40, 35, 2.54, True),
        Note("3S LiPo, 9.0-12.6 V. 100 A continuous / 150 A burst.", 40, 43),
        Note("D101 SMBJ20A: 20 V standoff clears 4S (16.8 V) and clamps", 40, 47),
        Note("at 32.4 V, below the 40 V FET rating.", 40, 51),
        Note("Ripple budget ~50 A RMS at 100 A: C101-103 carry ~8.4 A,", 180, 35),
        Note("the 24x 10uF MLCC array carries the rest. See ESC-001 --", 180, 39),
        Note("a low-ESR cap at the battery connector on SHORT leads is", 180, 43),
        Note("REQUIRED; lead inductance dominates, not the on-board bank.", 180, 47),
        Note("Reverse-polarity protection is deliberately ABSENT: an ideal-", 40, 130),
        Note("diode stage at 100 A costs ~0.5 mOhm and ~5 W plus its own", 40, 134),
        Note("gate drive. Mitigation is the polarised XT90. See ESC-006.", 40, 138),
    ]
    return Sheet("01_power_in.kicad_sch", "Power Input", "1",
                 title="Power Input and Bulk Capacitance",
                 comps=c, notes=notes)


def sheet_02_driver() -> Sheet:
    """DRV8323R: charge pump, buck regulator, config/SPI. Units 1 and 3."""
    c: list[Comp] = [
        act("U201", "DRV", 190, 110, unit=1),          # gate drive
        act("U201", "DRV", 190, 250, unit=3),          # logic / buck
        # charge pump + VM
        psv("C201", "C_47N",  120,  80, value="47n/50V"),
        psv("C202", "C_1U",   120, 100, value="1u/25V"),
        psv("C203", "C_100N", 120, 120),
        psv("C204", "C_10U",  120, 140),
        # buck regulator (LMR16006X core, see SNVSA13)
        psv("L201", "L_33U",  300, 215, rot=90),
        psv("D201", "D_SCH",  280, 240, rot=90),
        psv("C205", "C_100N", 300, 190, value="100n/16V"),
        psv("C206", "C_10U",  340, 230),
        psv("C207", "C_4U7",  120, 230),
        psv("R201", "R_33K2", 370, 215, rot=90),
        psv("R202", "R_10K",  370, 250, rot=90),
        # DVDD / VREF local decoupling
        psv("C208", "C_1U",   340, 270),
        # --- config network: populated for the RH (resistor) build ---
        psv("R203", "R_10K",  260, 290, rot=90, value="IDRIVE"),
        psv("R204", "R_10K",  280, 290, rot=90, value="VDS"),
        psv("R205", "R_10K",  300, 290, rot=90, value="MODE"),
        psv("R206", "R_10K",  320, 290, rot=90, value="GAIN"),
        # --- pull-ups: needed for the RS (SPI) build ---
        psv("R207", "R_10K",  260, 330, rot=90, value="10k SDO"),
        psv("R208", "R_10K",  280, 330, rot=90, value="10k nFAULT"),
        psv("R209", "R_10K",  300, 330, rot=90, value="10k EN pd"),
        # nSHDN input-UVLO divider
        psv("R210", "R_100K",  90, 250, rot=90),
        psv("R211", "R_10K",   90, 285, rot=90),
    ]
    notes = [
        Note("02  GATE DRIVER  -  DRV8323R (VQFN-48 RGZ)", 40, 35, 2.54, True),
        Note("DUAL BUILD. RH and RS are the same pinout; only pins 29-32", 40, 45),
        Note("differ (SLVSDJ3D Table 6-4):", 40, 49),
        Note("   pin 29  MODE / SDO     pin 31  VDS  / SCLK", 40, 53),
        Note("   pin 30  IDRIVE / SDI   pin 32  GAIN / nSCS", 40, 57),
        Note("Populate R203-R206 for RH; fit R207 and route SPI for RS.", 40, 61),
        Note("NEVER populate both -- see docs/gate-driver-config.md.", 40, 65),
        Note("High-side drive is a CHARGE PUMP, not a bootstrap, so 100%", 40, 340),
        Note("duty cycle is supported and the high-side FET stays fully", 40, 344),
        Note("enhanced at full throttle.", 40, 348),
        Note("Buck: 12 V -> 3V3 @600 mA. Vout = Vfb*(1+R201/R202).", 340, 330),
        Note("R201/R202 = 33.2k/10k. Vfb from SNVSA13 -- see ESC-007.", 340, 334),
    ]
    return Sheet("02_gate_driver.kicad_sch", "Gate Driver", "2",
                 title="DRV8323R Smart Gate Driver", comps=c, notes=notes)


def sheet_03_power_stage() -> Sheet:
    """12 N-channel MOSFETs: 2 in parallel on each of the 6 switch positions."""
    c: list[Comp] = []
    # Three phase columns; within each, two paralleled FETs side by side.
    # High side on top, low side below, gate network to the left of each.
    for i, ph in enumerate(PHASES):
        x = 95 + i * 165
        hi = 301 + i * 4          # Q301/302 = A high, Q303/304 = A low
        lo = hi + 2
        for k in range(2):        # two FETs in parallel per position
            c.append(act(f"Q{hi + k}", "FET", x + k * 76, 115))
            c.append(act(f"Q{lo + k}", "FET", x + k * 76, 250))
        # common gate resistor with its turn-off bypass diode stacked below
        c.append(psv(f"R{325 + i * 2}", "R_0R", x - 53, 100))
        c.append(psv(f"D{301 + i * 2}", "D_SCH", x - 53, 115))
        c.append(psv(f"R{326 + i * 2}", "R_0R", x - 53, 235))
        c.append(psv(f"D{302 + i * 2}", "D_SCH", x - 53, 250))
        # per-FET series gate resistor and gate-source pulldown
        for k in range(2):
            c.append(psv(f"R{301 + i * 4 + k}", "R_4R7", x + k * 76 - 23, 110))
            c.append(psv(f"R{303 + i * 4 + k}", "R_4R7", x + k * 76 - 23, 245))
            c.append(psv(f"R{313 + i * 4 + k}", "R_10K",
                         x + k * 76 - 23, 140, rot=90))
            c.append(psv(f"R{315 + i * 4 + k}", "R_10K",
                         x + k * 76 - 23, 275, rot=90))
        c.append(act(f"J{301 + i}", "TERM", x + 120, 183, value=f"PHASE_{ph}"))
    # low-side common shunt: 4x 1 mOhm 2512 in parallel = 0.25 mOhm
    c += row("RS", 301, "R_SHUNT", 4, 150, 330, dx=30.48, per_row=4)
    notes = [
        Note("03  POWER STAGE  -  12x N-channel, 2 per switch position",
             40, 35, 2.54, True),
        Note("TPHR8504PL 40 V / 0.85 mOhm max. 40 V on a 12.6 V bus is", 40, 45),
        Note("deliberate: a 150 A edge into ~5 nH of loop inductance adds", 40, 49),
        Note("7.5 V of overshoot and real layouts do worse.", 40, 53),
        Note("EVERY FET has its OWN series gate resistor. Two gates tied", 40, 325),
        Note("directly together resonate through their package inductance", 40, 329),
        Note("and oscillate -- separate resistors de-Q that loop. This is", 40, 333),
        Note("mandatory for paralleled FETs, not optional.", 40, 337),
        Note("Every FET also has a 10k gate-source pulldown, so a floating", 40, 345),
        Note("gate cannot be turned on through Cgd by drain dv/dt.", 40, 349),
        Note("Dxxx bypasses the common gate resistor on turn-OFF only, so", 400, 325),
        Note("turn-off is faster than turn-on -- this widens effective dead", 400, 329),
        Note("time. Asymmetry is in the safe direction. See shoot-through.md.", 400, 333),
        Note("RS301-304: 4x 1 mOhm 2512 = 0.25 mOhm, 12 W rating, 2.5 W", 400, 345),
        Note("dissipated at 100 A. Hottest discrete on the board.", 400, 349),
    ]
    return Sheet("03_power_stage.kicad_sch", "Power Stage", "3",
                 title="Three-Phase All-NMOS Bridge", comps=c, notes=notes)


def sheet_04_mcu() -> Sheet:
    c: list[Comp] = [
        act("U401", "MCU", 220, 160),
        psv("C401", "C_100N", 120, 100),
        psv("C402", "C_100N", 140, 100),
        psv("C403", "C_4U7",  160, 100),
        psv("C404", "C_100N", 120, 130, value="100n VREF+"),
        psv("C405", "C_1U",   140, 130, value="1u VREF+"),
        psv("C406", "C_100N", 120, 230, value="100n NRST"),
        psv("R401", "R_10K",  140, 230, rot=90),
        act("J401", "SWD", 400, 120),
        act("J402", "SIG", 400, 220),
        psv("R402", "R_1K",   250, 300, rot=90),
        psv("D401", "LED_G",  250, 320, rot=90),
    ]
    notes = [
        Note("04  MCU  -  STM32G071CBT6 (LQFP-48)", 40, 35, 2.54, True),
        Note("AM32 target: HARDWARE_GROUP_G0_A + NO_PA11_PA12_REMAP.", 40, 45),
        Note("On the 48-pin package PA9/PA10 are DEDICATED pins 29/32;", 40, 49),
        Note("pins 33/34 are PA11/PA12 and are left unconnected. AM32", 40, 53),
        Note("remaps by default, which is correct for 28/32-pin parts and", 40, 57),
        Note("WRONG here -- hence the define. See docs/pinout.md.", 40, 61),
        Note("Symbol is KiCad's STM32G081CBTx copied and renamed: the", 40, 300),
        Note("G081CB is the same die and bonding as the G071CB (DS12232", 40, 329),
        Note("covers both) and differs only by the AES block, which has", 40, 333),
        Note("no pins. Avoids hand-transcribing 48 pins.", 40, 337),
        Note("nFAULT lands on PB12 = TIM1_BKIN so a driver fault kills all", 400, 325),
        Note("six PWM outputs in HARDWARE. See ESC-003.", 400, 329),
    ]
    return Sheet("04_mcu.kicad_sch", "MCU", "4",
                 title="STM32G071 Controller", comps=c, notes=notes)


def sheet_05_sense() -> Sheet:
    """Back-EMF dividers, virtual neutral, bus voltage, current, temperature."""
    c: list[Comp] = [act("U201", "DRV", 380, 140, unit=2)]   # 3x CSA
    for i, ph in enumerate(PHASES):
        x = 80 + i * 60
        c.append(psv(f"R{501 + i}", "R_10K", x, 90, rot=90))
        c.append(psv(f"R{504 + i}", "R_1K",  x, 125, rot=90))
        c.append(psv(f"R{507 + i}", "R_10K", x, 190, rot=90))   # virtual neutral
    c += [
        psv("R510", "R_1K",   140, 230, rot=90),   # neutral shunt leg
        psv("R511", "R_100K", 260, 280, rot=90),   # VBAT divider top
        psv("R512", "R_10K",  260, 315, rot=90),   # VBAT divider bottom
        psv("C501", "C_100N", 290, 315),
        psv("R513", "NTC_10K", 80, 290, rot=90),
        psv("R514", "R_10K",   80, 325, rot=90),
        psv("C502", "C_100N", 110, 325),
        psv("C503", "C_100N", 440, 190, value="100n VREF"),
    ]
    notes = [
        Note("05  SENSE  -  back-EMF, bus voltage, current, temperature",
             40, 35, 2.54, True),
        Note("AM32 multiplexes ONE comparator (COMP2) across the three", 40, 45),
        Note("phases. Phase dividers drive COMP2_INM; the virtual neutral", 40, 49),
        Note("drives COMP2_INP on PA3. R507-509 + R510 synthesise the star", 40, 53),
        Note("point, which an unterminated wye or delta motor never brings", 40, 57),
        Note("out. Divider ratio 11:1 matches the phase dividers exactly --", 40, 61),
        Note("if they differ, zero-crossing detection is biased and timing", 40, 65),
        Note("drifts with throttle.", 40, 69),
        Note("Only CSA A is used (AM32 reads total bus current). SPB/SNB", 380, 280),
        Note("and SPC/SNC are tied to PGND per SLVSDJ3D Table 6-4: an", 380, 284),
        Note("unused CSA input must be tied, not left floating. Three", 380, 288),
        Note("separate shunts would enable per-phase FOC later at 3x the", 380, 292),
        Note("shunt dissipation -- deferred, not designed out.", 380, 296),
    ]
    return Sheet("05_sense.kicad_sch", "Sense", "5",
                 title="Back-EMF, Current and Voltage Sensing",
                 comps=c, notes=notes)


def sheet_06_protect() -> Sheet:
    """Six-gate cross-interlock between MCU and gate driver."""
    c: list[Comp] = []
    for i, ph in enumerate(PHASES):
        x = 80 + i * 150
        c.append(act(f"U{601 + i * 2}", "1G97", x, 110))        # high-side gate
        c.append(act(f"U{602 + i * 2}", "1G97", x, 210))        # low-side gate
        c.append(psv(f"C{601 + i * 2}", "C_100N", x + 40, 110))
        c.append(psv(f"C{602 + i * 2}", "C_100N", x + 40, 210))
        # 0R bypass links, so the interlock can be shorted out for test
        c.append(psv(f"R{601 + i * 2}", "R_0R", x, 160, value="0R BYP"))
        c.append(psv(f"R{602 + i * 2}", "R_0R", x, 260, value="0R BYP"))
        # pulldowns on the driver-side inputs
        c.append(psv(f"R{607 + i * 2}", "R_10K", x + 75, 130, rot=90))
        c.append(psv(f"R{608 + i * 2}", "R_10K", x + 75, 230, rot=90))
    notes = [
        Note("06  SHOOT-THROUGH INTERLOCK  (layer 3 of 4)", 40, 35, 2.54, True),
        Note("SN74LVC1G97 wired per datasheet SCES416N Figure 6,", 40, 45),
        Note("'2-Input AND Gate With One Inverted Input':", 40, 49),
        Note("   In0 (pin 3) = GND   ->   Y = In1 AND NOT In2", 40, 53),
        Note("   high side: In1=INHx_MCU, In2=INLx_MCU", 40, 57),
        Note("   low  side: In1=INLx_MCU, In2=INHx_MCU", 40, 61),
        Note("Both outputs cannot be high at once for ANY input pattern.", 40, 65),
        Note("This is combinational -- no state to corrupt.", 40, 69),
        Note("Largely redundant with the DRV8323R's own interlock, and", 40, 300),
        Note("here anyway for the two cases it does not cover: the window", 40, 329),
        Note("before ENABLE+SPI config, and a firmware bug selecting 3x or", 40, 333),
        Note("1x PWM mode (where INLx stops meaning 'low side on').", 40, 337),
        Note("R601-606 are 0R bypass links for characterisation. Fitting a", 40, 345),
        Note("bypass DEFEATS layer 3 -- do not ship a board with them in.", 40, 349),
        Note("R607-612 pull the driver inputs down, so a tri-stated or", 400, 325),
        Note("unpowered MCU commands 'off' rather than 'undefined'.", 400, 329),
    ]
    return Sheet("06_protection.kicad_sch", "Protection", "6",
                 title="Shoot-Through Interlock and Fault Path",
                 comps=c, notes=notes)


def build_sheets() -> list[Sheet]:
    return [sheet_01_power(), sheet_02_driver(), sheet_03_power_stage(),
            sheet_04_mcu(), sheet_05_sense(), sheet_06_protect()]


ROOT_NOTES = [
    Note("12 V / 100 A THREE-PHASE ALL-NMOS MOTOR DRIVER", 30, 22, 5.0, True),
    Note("DShot150/300/600/1200 via AM32 | STM32G071CBT6 + DRV8323R | "
         "12x N-channel MOSFET, 2 per switch position", 30, 30, 2.2),
    Note(f"Rev {REV}", 30, 36, 1.8),
    Note("SHOOT-THROUGH is prevented in four independent layers:", 30, 300, 2.2, True),
    Note("  1  TIM1 hardware dead-time generator, DEAD_TIME 40 = 625 ns", 30, 306, 1.8),
    Note("  2  DRV8323R internal cross-conduction lockout + 100 ns", 30, 311, 1.8),
    Note("  3  6x SN74LVC1G97 combinational interlock (sheet 06)", 30, 316, 1.8),
    Note("  4  gate-source pulldowns + per-FET series gate resistors", 30, 321, 1.8),
    Note("  0  nFAULT -> PB12/TIM1_BKIN kills all 6 outputs in hardware", 30, 326, 1.8),
    Note("Full budget and derivation: docs/shoot-through.md", 30, 333, 1.8),
    Note("100 A continuous / 150 A burst at 12.6 V = ~19 W / ~40 W", 300, 300, 2.2, True),
    Note("dissipated. Needs forced air -- see docs/power-budget.md.", 300, 306, 1.8),
    Note("Firmware: AM32, HARDWARE_GROUP_G0_A + NO_PA11_PA12_REMAP.", 300, 316, 1.8),
    Note("See firmware/README.md for the target block and the", 300, 321, 1.8),
    Note("DRV8323RS SPI init that AM32 does not ship.", 300, 326, 1.8),
]


def generate(verify_only: bool = False) -> int:
    sheets = build_sheets()
    cache = SymbolCache({PROJ_LIB: DESIGN / "lib" / f"{PROJ_LIB}.kicad_sym"})

    all_lib_ids = sorted({c.lib_id for s in sheets for c in s.comps})
    for lib_id in all_lib_ids:
        cache.definition(lib_id)

    by_file = {s.filename: s for s in sheets}
    for filename, wire in wire_sheets.WIRE_PASSES.items():
        sheet = by_file.get(filename)
        if sheet is None:
            raise KeyError(f"WIRE_PASSES names an unknown sheet {filename!r}")
        wire(sheet, cache)

    comps = [(s, c) for s in sheets for c in s.comps]
    failures = list(cache.missing)

    for s, c in comps:
        for key in ("Footprint", "MPN", "LCSC"):
            if not c.props.get(key):
                failures.append(f"{s.filename}: {c.ref} missing {key}")

    by_ref: dict[str, list] = {}
    for s, c in comps:
        by_ref.setdefault(c.ref, []).append((s, c))
    for ref, entries in by_ref.items():
        if len(entries) == 1:
            continue
        lib_ids = {c.lib_id for _, c in entries}
        units = [c.unit for _, c in entries]
        if len(lib_ids) > 1:
            failures.append(f"{ref} reused across different symbols: {lib_ids}")
        elif len(units) != len(set(units)):
            dup = sorted(u for u in set(units) if units.count(u) > 1)
            failures.append(f"{ref} placed twice on unit(s) {dup}")

    # A net named as both a local and a global label is two nets that look
    # like one. Catch it here; ERC's own check is easy to miss in a pile.
    local = {lb.text for s in sheets for lb in s.labels if lb.kind == "local"}
    glob = {lb.text for s in sheets for lb in s.labels if lb.kind == "global"}
    for name in sorted(local & glob):
        failures.append(f"net {name!r} is labelled BOTH local and global")

    if verify_only:
        print(f"project    : {PROJECT}  rev {REV}")
        print(f"sheets     : {len(sheets)} + root")
        print(f"components : {len(comps)} placements, "
              f"{len(by_ref)} reference designators")
        print(f"symbols    : {len(all_lib_ids)} distinct, "
              f"{len(cache.missing)} unresolved")
        print()
        hdr = (f"{'sheet':<26} {'page':>4} {'parts':>6} {'notes':>6} "
               f"{'wires':>6} {'labels':>7} {'pwr':>5} {'NC':>4}")
        print(hdr); print("-" * len(hdr))
        for s in sheets:
            print(f"{s.filename:<26} {s.page:>4} {len(s.comps):>6} "
                  f"{len(s.notes):>6} {len(s.wires):>6} {len(s.labels):>7} "
                  f"{len(s.powers):>5} {len(s.no_connects):>4}")
        print("-" * len(hdr))
        print(f"{'TOTAL':<26} {'':>4} {len(comps):>6} "
              f"{sum(len(s.notes) for s in sheets):>6} "
              f"{sum(len(s.wires) for s in sheets):>6} "
              f"{sum(len(s.labels) for s in sheets):>7} "
              f"{sum(len(s.powers) for s in sheets):>5} "
              f"{sum(len(s.no_connects) for s in sheets):>4}")
        print()
        for ref, e in sorted((r, e) for r, e in by_ref.items() if len(e) > 1):
            print(f"multi-unit {ref}: units {sorted(c.unit for _, c in e)}")
        print()
        if failures:
            print("FAIL")
            for f in failures[:40]:
                print(f"  - {f}")
            if len(failures) > 40:
                print(f"  ... and {len(failures) - 40} more")
            return 1
        print("PASS  symbols resolve, every part has Footprint/MPN/LCSC, "
              "no reference collisions, no local/global net aliases")
        return 0

    if failures:
        print("refusing to write - verification failed:")
        for f in failures[:20]:
            print(f"  - {f}")
        return 1

    DESIGN.mkdir(parents=True, exist_ok=True)
    write_root(
        DESIGN / f"{PROJECT}.kicad_sch", sheets, PROJECT, ROOT_UUID,
        "12V 100A Three-Phase All-NMOS Motor Driver", REV, COMPANY,
        ["Top sheet - hierarchy overview",
         "STM32G071CBT6 + DRV8323R | 12x TPHR8504PL | DShot via AM32"],
        ROOT_NOTES,
    )
    # One shared counter dict: power-symbol refs must be unique across the
    # whole project, not per sheet.
    pwr_counters: dict[str, int] = {}
    for s in sheets:
        write_sheet(DESIGN / s.filename, s, cache, PROJECT, ROOT_UUID,
                    REV, COMPANY, pwr_counters)
    write_project(DESIGN / f"{PROJECT}.kicad_pro", PROJECT, sheets, ROOT_UUID)
    write_lib_tables(
        DESIGN,
        [(PROJ_LIB, f"${{KIPRJMOD}}/lib/{PROJ_LIB}.kicad_sym",
          "Project symbols: DRV8323R (48-pin RGZ), STM32G071CBTx")],
        [],
    )
    print(f"wrote {len(sheets) + 1} schematics, project file and lib tables")
    print(f"  {len(comps)} component placements, "
          f"{len(by_ref)} reference designators")
    return 0


def main() -> int:
    return generate(verify_only="--verify" in sys.argv)


if __name__ == "__main__":
    sys.exit(main())
