#!/usr/bin/env python3
"""Power/thermal budget. Regenerates the tables in docs/power-budget.md."""
import math

V_BUS = 12.6
I_CONT, I_BURST = 100.0, 150.0
FETS_PARALLEL = 6 * 2

RDSON_MAX_25C = 0.85e-3      # TPHR8504PL @ Vgs=10V -- VERIFY from datasheet
RDSON_HOT_MULT = 1.5         # normalised R_DS(on) vs Tj curve @125C
R_SHUNT = 0.25e-3            # 4x 1 mOhm 2512 in parallel
T_RISE = T_FALL = 100e-9
QG_POS_NC = 206.0
VGS = 10.0


def conduction(i_phase):
    """6-step: each position conducts 120 deg of 360 -> duty 1/3."""
    i_pos = i_phase * math.sqrt(1 / 3)
    i_fet = i_pos / 2
    r_hot = RDSON_MAX_25C * RDSON_HOT_MULT
    p_fet = i_fet ** 2 * r_hot
    return i_pos, i_fet, p_fet, p_fet * FETS_PARALLEL


def switching(i_phase, f_pwm):
    e = 0.5 * V_BUS * i_phase * (T_RISE + T_FALL)
    return e, e * f_pwm


def main():
    for label, i, f in (("100 A continuous", I_CONT, 24e3),
                        ("150 A burst (10 s)", I_BURST, 24e3)):
        i_pos, i_fet, p_fet, p_cond = conduction(i)
        _, p_sw = switching(i, f)
        p_shunt = i ** 2 * R_SHUNT
        p_gate = QG_POS_NC * 1e-9 * VGS * f * 6
        p_misc = 0.6
        total = p_cond + p_sw + p_shunt + p_gate + p_misc
        print(f"\n=== {label}  @ {f/1e3:.0f} kHz, {V_BUS} V ===")
        print(f"  I_rms per position  : {i_pos:6.1f} A")
        print(f"  I_rms per FET       : {i_fet:6.1f} A   ({FETS_PARALLEL} FETs)")
        print(f"  Conduction          : {p_cond:6.1f} W   ({p_fet:.2f} W/FET)")
        print(f"  Switching           : {p_sw:6.1f} W")
        print(f"  Shunt               : {p_shunt:6.1f} W")
        print(f"  Gate drive          : {p_gate:6.2f} W")
        print(f"  Driver + MCU + buck : {p_misc:6.1f} W")
        print(f"  TOTAL               : {total:6.1f} W   ({i*V_BUS:.0f} W delivered,"
              f" {100*(1-total/(i*V_BUS)):.1f}% efficient)")

    print("\n=== switching loss vs PWM frequency @100 A ===")
    for f in (16e3, 24e3, 32e3, 48e3):
        _, p = switching(I_CONT, f)
        print(f"  {f/1e3:>4.0f} kHz : {p:5.1f} W")

    print("\n=== input ripple ===")
    print(f"  worst-case RMS ~ 0.5 * I_dc = {0.5*I_CONT:.0f} A  (see ESC-001)")


if __name__ == "__main__":
    main()
