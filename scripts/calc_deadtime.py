#!/usr/bin/env python3
"""Dead-time budget for the DShot ESC. Regenerates the tables in
docs/shoot-through.md.

AM32's `DEAD_TIME` target define is written straight into TIM1's
BDTR.DTG[7:0] register field -- it is NOT nanoseconds. Everything here
derives from that fact plus AM32's clock tree, both verified in
Mcu/g071/Src/peripherals.c:
    HSI 16 MHz -> PLL(M=1, N=8, R=2) = 64 MHz, AHB /1,
    TIM1 Prescaler = 0, ClockDivision = DIV1.
"""
TIM1_HZ = 64e6
T_DTS = 1.0 / TIM1_HZ          # 15.625 ns


def dtg_to_seconds(dtg: int) -> float:
    """RM0444 (STM32G0 reference manual), TIMx_BDTR DTG[7:0] encoding."""
    if not 0 <= dtg <= 255:
        raise ValueError(f"DTG must be 0..255, got {dtg}")
    top = dtg >> 5
    if top <= 3:                       # 0xx : linear
        return dtg * T_DTS
    if top <= 5:                       # 10x
        return (64 + (dtg & 0x3F)) * 2 * T_DTS
    if top == 6:                       # 110
        return (32 + (dtg & 0x1F)) * 8 * T_DTS
    return (32 + (dtg & 0x1F)) * 16 * T_DTS   # 111


# ---- FET / driver parameters (TPHR8504PL x2 per switch position) ----
# Verified against the Toshiba TPHR8504PL datasheet, Electrical
# Characteristics (VDD ~20 V, VGS = 10 V, ID = 50 A):
#     Qg   = 103   nC      total gate charge
#     Qgs1 =  25   nC      gate-source charge to the Miller plateau
#     Qgd  =  12.4 nC      gate-drain (Miller) charge
QG_PER_FET_NC = 103.0
QGS1_PER_FET_NC = 25.0
QGD_PER_FET_NC = 12.4
FETS_PARALLEL = 2
I_SINK_A = 1.0            # DRV8323 IDRIVEN setting
I_SOURCE_A = 0.30         # DRV8323 IDRIVEP setting
T_PD_NS = 100.0           # DRV8323 INx->Gx propagation delay -- VERIFY (ESC-009)


def budget():
    qg = QG_PER_FET_NC * FETS_PARALLEL
    qgs1 = QGS1_PER_FET_NC * FETS_PARALLEL
    t_off = T_PD_NS + (qg - qgs1) / I_SINK_A          # nC/A == ns
    t_on_delay = T_PD_NS + qgs1 / I_SOURCE_A
    return qg, t_off, t_on_delay, t_off - t_on_delay


def idrive():
    """DRV8323 datasheet SLVSDJ3D Eq. 11/12: IDRIVE > Qgd / t_edge."""
    qgd = QGD_PER_FET_NC * FETS_PARALLEL
    return qgd, qgd / 100.0, qgd / 50.0        # nC/ns == A


def main():
    print(f"t_DTS = {T_DTS*1e9:.3f} ns  (TIM1 @ {TIM1_HZ/1e6:.0f} MHz, PSC=0, CKD=1)\n")
    print(f"{'DEAD_TIME':>10} {'dead time':>12} {'@24kHz':>9} {'@48kHz':>9}")
    for n in (16, 24, 32, 40, 48, 60, 80, 120, 127, 160, 210):
        dt = dtg_to_seconds(n)
        print(f"{n:>10} {dt*1e9:>9.1f} ns {dt*24e3*100:>8.2f}% {dt*48e3*100:>8.2f}%")

    qg, t_off, t_on, net = budget()
    print(f"\nGate charge per position : {qg:.0f} nC ({FETS_PARALLEL} x {QG_PER_FET_NC:.0f} nC)")
    print(f"t_off  (outgoing FET)    : {t_off:.0f} ns")
    print(f"t_on_delay (incoming)    : {t_on:.0f} ns")
    print(f"NET requirement          : {net:.0f} ns")

    qgd, ip_100, in_50 = idrive()
    print(f"\nMiller charge per position : {qgd:.1f} nC")
    print(f"  IDRIVEP for a 100 ns rise : {ip_100*1e3:.0f} mA"
          f"   (setting: {I_SOURCE_A*1e3:.0f} mA)")
    print(f"  IDRIVEN for a  50 ns fall : {in_50*1e3:.0f} mA"
          f"   (setting: {I_SINK_A*1e3:.0f} mA)")

    chosen = 40
    dt = dtg_to_seconds(chosen)
    print(f"\nSHIPPED: DEAD_TIME {chosen} = {dt*1e9:.0f} ns")
    if net <= 0:
        print("  The net requirement is NEGATIVE: with IDRIVEN 3.3x IDRIVEP,")
        print("  turn-off already completes before turn-on begins, so under")
        print("  nominal conditions the bridge cannot cross-conduct at all.")
        print("  The 625 ns therefore exists ENTIRELY as margin against Vth")
        print("  spread across 12 FETs, Qg/Rds(on) tempco over a 150 C swing,")
        print("  paralleled gates not switching in unison, and gate ringing.")
    else:
        print(f"  -> {dt*1e9/net:.1f}x margin on the net requirement")

    # Charge-pump ceiling: DRV8323 datasheet SLVSDJ3D Eq. 9 (trapezoidal)
    print("\nCharge-pump headroom (I_VCP > Qg * f_PWM, I_VCP >= 15 mA):")
    for f in (24e3, 48e3):
        need = qg * 1e-9 * f
        print(f"  {f/1e3:>4.0f} kHz : {need*1e3:5.2f} mA required"
              f"  -> {15e-3/need:.1f}x margin")


if __name__ == "__main__":
    main()
