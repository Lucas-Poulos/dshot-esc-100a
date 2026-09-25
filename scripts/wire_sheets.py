#!/usr/bin/env python3
"""Connectivity for every sheet, one function per sheet.

Nets are made by NAME, not by drawing polylines between pins: each pin gets
a one-grid stub and a label, and identically spelled labels are one net.
KiCad's netlister treats the two forms as identical, and hand-routing a
12-MOSFET bridge as wires is not tractable.

Rail names are constants because a misspelled rail silently becomes a
second, unconnected net that looks completely normal on screen.
"""
from __future__ import annotations

from kicad_sch import Sheet, SymbolCache, Wirer

# -- rails (power symbols; global by construction) -------------------------
VBATT = "+BATT"        # 12 V battery rail
V3V3 = "+3V3"          # logic rail, from the DRV8323R buck
GND = "GND"

# -- cross-sheet nets (global labels) --------------------------------------
SHUNT_P = "SHUNT_P"    # common low-side source, above the shunt
PHASE = {p: f"PHASE_{p}" for p in "ABC"}
GH = {p: f"GH{p}" for p in "ABC"}      # driver -> high-side gate network
GL = {p: f"GL{p}" for p in "ABC"}
# MCU -> interlock -> driver
INH_MCU = {p: f"INH{p}_MCU" for p in "ABC"}
INL_MCU = {p: f"INL{p}_MCU" for p in "ABC"}
INH_DRV = {p: f"INH{p}" for p in "ABC"}
INL_DRV = {p: f"INL{p}" for p in "ABC"}
# sense
BEMF = {p: f"BEMF_{p}" for p in "ABC"}
V_NEUTRAL = "V_NEUTRAL"
ADC_BUSV = "ADC_BUSV"
ADC_CURRENT = "ADC_CURRENT"
ADC_TEMP = "ADC_TEMP"
# driver control
DRV_ENABLE, DRV_NFAULT, DRV_CAL = "DRV_ENABLE", "DRV_nFAULT", "DRV_CAL"
DRV_SCLK, DRV_SDI, DRV_SDO, DRV_NSCS = "DRV_SCLK", "DRV_SDI", "DRV_SDO", "DRV_nSCS"
DVDD, VREF = "DVDD", "VREF"
SW_NODE, FB_NODE, NSHDN = "SW", "FB", "nSHDN"
# MCU
DSHOT_IN, TELEM = "DSHOT_IN", "TELEM"
SWDIO, SWCLK, NRST = "SWDIO", "SWCLK", "NRST"
LED_STATUS = "LED_STATUS"

PH = ("A", "B", "C")


# ==========================================================================
def wire_01_power(sheet: Sheet, cache: SymbolCache) -> None:
    w = Wirer(sheet, cache)
    w.power("J101", "1", VBATT)
    w.power("J102", "1", GND)
    # TVS across the rail
    w.power("D101", "A1", VBATT)
    w.power("D101", "A2", GND)
    # bulk electrolytics + the distributed MLCC array
    for ref in ("C101", "C102", "C103"):
        w.power(ref, "1", VBATT)
        w.power(ref, "2", GND)
    for i in range(24):
        ref = f"C{104 + i}"
        w.power(ref, "1", VBATT)
        w.power(ref, "2", GND)
    # The battery is the only source on this net that KiCad can see, and a
    # connector pin is typed passive, so ERC needs telling it is driven.
    w.flag(VBATT, 40, 200)
    w.flag(GND, 70, 200)


# ==========================================================================
def wire_02_driver(sheet: Sheet, cache: SymbolCache) -> None:
    w = Wirer(sheet, cache)
    U, u1, u3 = "U201", 1, 3

    # ---- unit 1: charge pump, supplies, gate outputs ----
    w.power(U, "VM", VBATT, unit=u1)
    w.power(U, "PGND", GND, unit=u1)
    # VDRAIN senses the common high-side drain, which is the battery rail.
    w.power(U, "VDRAIN", VBATT, unit=u1)
    # CPH/CPL flying cap; VCP reservoir to VM
    w.net("CPH", (U, "CPH", u1), ("C201", "1"))
    w.net("CPL", (U, "CPL", u1), ("C201", "2"))
    w.rail("VCP", (U, "VCP", u1), ("C202", "1"))
    w.power("C202", "2", VBATT)
    for ref in ("C203", "C204"):
        w.power(ref, "1", VBATT)
        w.power(ref, "2", GND)
    for p in PH:
        w.rail(GH[p], (U, f"GH{p}", u1))
        w.rail(GL[p], (U, f"GL{p}", u1))
        # SHx IS the phase node -- one net, one name, no alias.
        w.rail(PHASE[p], (U, f"SH{p}", u1))

    # ---- unit 3: logic inputs, config/SPI, buck ----
    for p in PH:
        w.rail(INH_DRV[p], (U, f"INH{p}", u3))
        w.rail(INL_DRV[p], (U, f"INL{p}", u3))
    w.rail(DRV_ENABLE, (U, "ENABLE", u3), ("R209", "1"))
    w.power("R209", "2", GND)
    w.rail(DRV_NFAULT, (U, "nFAULT", u3), ("R208", "1"))
    w.power("R208", "2", V3V3)

    # Pins 29-32 carry the RH config resistors AND the RS SPI net. Exactly
    # one set is populated; see docs/gate-driver-config.md.
    w.rail(DRV_SDO,  (U, "MODE/SDO", u3),  ("R205", "1"), ("R207", "1"))
    w.rail(DRV_SDI,  (U, "IDRIVE/SDI", u3), ("R203", "1"))
    w.rail(DRV_SCLK, (U, "VDS/SCLK", u3),  ("R204", "1"))
    w.rail(DRV_NSCS, (U, "GAIN/nSCS", u3), ("R206", "1"))
    w.power("R207", "2", V3V3)
    for ref in ("R203", "R204", "R205", "R206"):
        w.power(ref, "2", GND)

    w.rail(DVDD, (U, "DVDD", u3), ("C208", "1"))
    w.power("C208", "2", GND)

    # buck: VIN from the battery, SW -> L -> 3V3, catch diode to ground
    w.power(U, "VIN", VBATT, unit=u3)
    w.power("C207", "1", VBATT)
    w.power("C207", "2", GND)
    # Catch diode: cathode on SW, anode to ground (non-synchronous buck).
    w.net(SW_NODE, (U, "SW", u3), ("L201", "1"), ("D201", "K"), ("C205", "2"))
    w.power("D201", "A", GND)
    w.net("CB", (U, "CB", u3), ("C205", "1"))
    w.power("L201", "2", V3V3)
    w.power("C206", "1", V3V3)
    w.power("C206", "2", GND)
    w.net(FB_NODE, (U, "FB", u3), ("R201", "2"), ("R202", "1"))
    w.power("R201", "1", V3V3)
    w.power("R202", "2", GND)
    # nSHDN: input UVLO divider off the battery rail
    w.net(NSHDN, (U, "nSHDN", u3), ("R210", "2"), ("R211", "1"))
    w.power("R210", "1", VBATT)
    w.power("R211", "2", GND)

    w.no_connect(U, "NC", unit=u3)
    for pin in ("DGND", "BGND", "PAD"):
        w.power(U, pin, GND, unit=u3)
    # The buck output is this board's only 3V3 source and KiCad cannot see
    # an inductor as a supply, so the rail needs a flag.
    w.flag(V3V3, 430, 250)


# ==========================================================================
def wire_03_power_stage(sheet: Sheet, cache: SymbolCache) -> None:
    w = Wirer(sheet, cache)
    for i, p in enumerate(PH):
        hi, lo = 301 + i * 4, 303 + i * 4
        rc_h, rc_l = f"R{325 + i * 2}", f"R{326 + i * 2}"
        d_h, d_l = f"D{301 + i * 2}", f"D{302 + i * 2}"
        gate_h, gate_l = f"GH{p}_G", f"GL{p}_G"

        # common gate resistor, with a Schottky bypassing it on turn-OFF
        # only (anode at the gate node, cathode back to the driver).
        # Anode on the GATE node, cathode back at the DRIVER pin, so the
        # diode conducts only while the driver is sinking the gate down.
        w.rail(GH[p], (rc_h, "1"), (d_h, "K"))
        w.net(gate_h, (rc_h, "2"), (d_h, "A"))
        w.rail(GL[p], (rc_l, "1"), (d_l, "K"))
        w.net(gate_l, (rc_l, "2"), (d_l, "A"))

        for k in range(2):
            qh, ql = f"Q{hi + k}", f"Q{lo + k}"
            rgh, rgl = f"R{301 + i * 4 + k}", f"R{303 + i * 4 + k}"
            pdh, pdl = f"R{313 + i * 4 + k}", f"R{315 + i * 4 + k}"

            # --- high side: drain on the battery rail, source on the phase
            w.net(gate_h, (rgh, "1"))
            w.net(f"G{qh}", (rgh, "2"), (qh, "G"), (pdh, "1"))
            w.power(qh, "D", VBATT)
            w.rail(PHASE[p], (qh, "S"))
            # gate-source pulldown must return to the SOURCE, not to GND
            w.rail(PHASE[p], (pdh, "2"))

            # --- low side: drain on the phase, source on the shunt node
            w.net(gate_l, (rgl, "1"))
            w.net(f"G{ql}", (rgl, "2"), (ql, "G"), (pdl, "1"))
            w.rail(PHASE[p], (ql, "D"))
            w.rail(SHUNT_P, (ql, "S"), (pdl, "2"))

        # motor terminal
        w.rail(PHASE[p], (f"J{301 + i}", "1"))

    # common low-side shunt: 4x 1 mOhm in parallel
    for i in range(4):
        ref = f"RS{301 + i}"
        w.rail(SHUNT_P, (ref, "1"))
        w.power(ref, "2", GND)


# ==========================================================================
def wire_04_mcu(sheet: Sheet, cache: SymbolCache) -> None:
    """Pins are addressed by NUMBER, not name.

    PA9 and PA10 each appear twice in the 48-pin symbol -- as the dedicated
    pins 29/32 and again as the remappable PA11/PA12 pads 33/34. Addressing
    by name would be ambiguous, and picking the wrong one puts a PWM output
    on an unbonded pad.
    """
    w = Wirer(sheet, cache)
    M = "U401"

    # supplies
    w.power(M, "6", V3V3)          # VDD
    w.power(M, "4", V3V3)          # VBAT -> tied to VDD
    w.power(M, "5", V3V3)          # VREF+ (see note: ferrite is ESC-008)
    w.power(M, "7", GND)           # VSS
    for ref in ("C401", "C402", "C403", "C404", "C405"):
        w.power(ref, "1", V3V3)
        w.power(ref, "2", GND)

    # reset
    w.rail(NRST, (M, "10"), ("C406", "1"), ("R401", "2"))
    w.power("C406", "2", GND)
    w.power("R401", "1", V3V3)

    # --- TIM1 complementary PWM -> interlock (sheet 06) ---
    w.rail(INH_MCU["A"], (M, "32"))                               # PA10 TIM1_CH3
    w.rail(INL_MCU["A"], (M, "20"))                               # PB1  TIM1_CH3N
    w.rail(INH_MCU["B"], (M, "29"))                               # PA9  TIM1_CH2
    w.rail(INL_MCU["B"], (M, "19"))                               # PB0  TIM1_CH2N
    w.rail(INH_MCU["C"], (M, "28"))                               # PA8  TIM1_CH1
    w.rail(INL_MCU["C"], (M, "18"))                               # PA7  TIM1_CH1N
    # PA11 / PA12 pads are unused because NO_PA11_PA12_REMAP is set
    w.no_connect(M, "33")
    w.no_connect(M, "34")

    # --- sensorless comparator inputs ---
    w.rail(BEMF["A"], (M, "46"))       # PB7 COMP2_INM IO2
    w.rail(BEMF["B"], (M, "42"))       # PB3 COMP2_INM IO1
    w.rail(BEMF["C"], (M, "13"))       # PA2 COMP2_INM IO3
    w.rail(V_NEUTRAL, (M, "14"))       # PA3 COMP2_INP IO3

    # --- ADC ---
    w.rail(ADC_BUSV, (M, "15"))      # PA4 ADC_IN4
    w.rail(ADC_CURRENT, (M, "17"))         # PA6 ADC_IN6
    w.rail(ADC_TEMP, (M, "12"))       # PA1 ADC_IN1

    # --- gate driver control ---
    w.rail(DRV_NSCS, (M, "11"))        # PA0
    w.rail(DRV_SDO, (M, "21"))         # PB2
    w.rail(DRV_SCLK, (M, "22"))        # PB10
    w.rail(DRV_SDI, (M, "23"))         # PB11
    w.rail(DRV_NFAULT, (M, "24"))      # PB12 TIM1_BKIN
    w.rail(DRV_ENABLE, (M, "25"))      # PB13
    w.rail(DRV_CAL, (M, "26"))         # PB14

    # --- host interface + debug ---
    w.rail(DSHOT_IN, (M, "43"))        # PB4 TIM3_CH1 + DMA1_CH1
    w.rail(TELEM, (M, "45"))           # PB6 USART1 AF0, one-wire
    w.rail(SWDIO, (M, "35"))           # PA13
    w.rail(SWCLK, (M, "36"))           # PA14
    w.rail(LED_STATUS, (M, "30"))      # PC6

    # unused pins
    for pin in ("1", "2", "3", "8", "9", "16", "27", "31", "37",
                "38", "39", "40", "41", "44", "47", "48"):
        w.no_connect(M, pin)

    # SWD header (2x05 1.27mm, ARM Cortex Debug pinout)
    w.power("J401", "1", V3V3)
    w.rail(SWDIO, ("J401", "2"))
    w.power("J401", "3", GND)
    w.rail(SWCLK, ("J401", "4"))
    w.power("J401", "5", GND)
    for pin in ("6", "7", "8"):
        w.no_connect("J401", pin)
    w.power("J401", "9", GND)
    w.rail(NRST, ("J401", "10"))

    # signal / telemetry header
    w.rail(DSHOT_IN, ("J402", "1"))
    w.rail(TELEM, ("J402", "2"))
    w.power("J402", "3", GND)
    w.power("J402", "4", V3V3)

    # status LED
    w.rail(LED_STATUS, ("R402", "1"))
    w.net("LED_A", ("R402", "2"), ("D401", "A"))
    w.power("D401", "K", GND)


# ==========================================================================
def wire_05_sense(sheet: Sheet, cache: SymbolCache) -> None:
    w = Wirer(sheet, cache)
    U, u2 = "U201", 2

    # Back-EMF dividers, 10k/1k = 11:1. The virtual-neutral divider MUST
    # use the same ratio or zero-crossing detection is biased.
    for i, p in enumerate(PH):
        rt, rb, rn = f"R{501 + i}", f"R{504 + i}", f"R{507 + i}"
        w.rail(PHASE[p], (rt, "1"))
        w.rail(BEMF[p], (rt, "2"), (rb, "1"))
        w.power(rb, "2", GND)
        # virtual star point
        w.rail(PHASE[p], (rn, "1"))
        w.rail(V_NEUTRAL, (rn, "2"))
    w.rail(V_NEUTRAL, ("R510", "1"))
    w.power("R510", "2", GND)

    # bus voltage divider 100k/10k = 11:1  -> 36 V full scale on a 3V3 ADC
    w.power("R511", "1", VBATT)
    w.rail(ADC_BUSV, ("R511", "2"), ("R512", "1"), ("C501", "1"))
    w.power("R512", "2", GND)
    w.power("C501", "2", GND)

    # NTC divider: NTC on top, 10k to ground
    w.power("R513", "1", V3V3)
    w.rail(ADC_TEMP, ("R513", "2"), ("R514", "1"), ("C502", "1"))
    w.power("R514", "2", GND)
    w.power("C502", "2", GND)

    # ---- DRV8323R current sense amplifiers (unit 2) ----
    # CSA A reads the common shunt. B and C are unused and must be TIED,
    # not floated (SLVSDJ3D Table 6-4: "If CSA is not used tie to PGND").
    w.rail(SHUNT_P, (U, "SPA", u2))
    w.power(U, "SNA", GND, unit=u2)
    w.rail(ADC_CURRENT, (U, "SOA", u2))
    for pin in ("SPB", "SNB", "SPC", "SNC"):
        w.power(U, pin, GND, unit=u2)
    w.no_connect(U, "SOB", unit=u2)
    w.no_connect(U, "SOC", unit=u2)
    w.power(U, "VREF", V3V3, unit=u2)
    w.power("C503", "1", V3V3)
    w.power("C503", "2", GND)
    w.rail(DRV_CAL, (U, "CAL", u2))
    w.power(U, "AGND", GND, unit=u2)


# ==========================================================================
def wire_06_protect(sheet: Sheet, cache: SymbolCache) -> None:
    """SN74LVC1G97 per SCES416N Figure 6: In0=GND -> Y = In1 AND NOT In2."""
    w = Wirer(sheet, cache)
    for i, p in enumerate(PH):
        gh, gl = f"U{601 + i * 2}", f"U{602 + i * 2}"
        ch, cl = f"C{601 + i * 2}", f"C{602 + i * 2}"
        byp_h, byp_l = f"R{601 + i * 2}", f"R{602 + i * 2}"
        pd_h, pd_l = f"R{607 + i * 2}", f"R{608 + i * 2}"

        for g, c in ((gh, ch), (gl, cl)):
            w.power(g, "VCC", V3V3)
            w.power(g, "GND", GND)
            w.power(g, "IN0", GND)      # Figure 6 tie-off
            w.power(c, "1", V3V3)
            w.power(c, "2", GND)

        # high-side gate: Y = INH AND NOT INL
        w.rail(INH_MCU[p], (gh, "IN1"), (byp_h, "1"))
        w.rail(INL_MCU[p], (gh, "IN2"))
        w.rail(INH_DRV[p], (gh, "Y"), (byp_h, "2"), (pd_h, "1"))
        w.power(pd_h, "2", GND)

        # low-side gate: Y = INL AND NOT INH
        w.rail(INL_MCU[p], (gl, "IN1"), (byp_l, "1"))
        w.rail(INH_MCU[p], (gl, "IN2"))
        w.rail(INL_DRV[p], (gl, "Y"), (byp_l, "2"), (pd_l, "1"))
        w.power(pd_l, "2", GND)


WIRE_PASSES = {
    "01_power_in.kicad_sch": wire_01_power,
    "02_gate_driver.kicad_sch": wire_02_driver,
    "03_power_stage.kicad_sch": wire_03_power_stage,
    "04_mcu.kicad_sch": wire_04_mcu,
    "05_sense.kicad_sch": wire_05_sense,
    "06_protection.kicad_sch": wire_06_protect,
}
