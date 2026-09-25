# Shoot-Through Prevention and Dead Time

Shoot-through is the failure where the high-side and low-side FETs of one
half-bridge are on simultaneously, putting the battery across two FETs with
nothing but their R_DS(on) in the path. At 12 V into 2 x 0.43 mOhm that is
roughly **14 kA**, limited only by parasitic inductance. It destroys the
bridge in microseconds and there is no fuse fast enough. So it is prevented
in four independent layers, no one of which is trusted alone.

---

## Layer 1 — TIM1 hardware dead-time generator (primary)

The STM32G071's advanced timer generates the complementary pair in
**hardware**. Firmware writes one duty value; the timer derives `CHxN` as
the inverse with a guaranteed non-overlap window inserted on both edges.
Because it is a hardware state machine, no firmware bug, interrupt storm,
or stalled loop can make the two outputs overlap.

AM32 sets this through `TIM_BDTRInitStruct.DeadTime = DEAD_TIME`, which is
the **raw DTG[7:0] register value**, not nanoseconds. The conversion is
load-bearing and easy to get wrong, so it is derived here rather than
assumed.

AM32 configures the STM32G071 at `HSI 16 MHz -> PLL(M=1, N=8, R=2) = 64 MHz`,
with `SYSCLK` undivided, `TIM1 Prescaler = 0` and
`ClockDivision = DIV1`. Therefore:

```
t_DTS = 1 / 64 MHz = 15.625 ns
```

With `DTG[7:5] = 0xx` (i.e. DEAD_TIME <= 127) the reference manual gives
`DT = DTG[7:0] x t_DTS`:

| `DEAD_TIME` | Dead time | Duty loss @24 kHz | @48 kHz |
|---:|---:|---:|---:|
| 24 | 375 ns | 0.9 % | 1.8 % |
| 32 | 500 ns | 1.2 % | 2.4 % |
| **40** | **625 ns** | **1.5 %** | **3.0 %** |
| 60 | 938 ns | 2.3 % | 4.5 % |
| 80 | 1250 ns | 3.0 % | 6.0 % |

Above 127 the encoding changes slope, which is why the AM32 `DT160` and
`DT210` targets land at 3.0 us and 6.25 us rather than anything linear.

**This board ships `DEAD_TIME 40` (625 ns).** Justification in the budget
below; `scripts/calc_deadtime.py` regenerates this table.

## The dead-time budget

Dead time must outlast the slowest turn-off, because the *outgoing* FET has
to be fully off before the *incoming* one starts conducting:

```
DT_required  >  t_off(outgoing) - t_on_delay(incoming) + margin
```

For two TPHR8504PL in parallel per position, driven at `IDRIVEN` = 1 A
sink and `IDRIVEP` = 300 mA source. Gate-charge figures are read from the
Toshiba TPHR8504PL datasheet Electrical Characteristics table
(VDD ~20 V, V_GS = 10 V, I_D = 50 A): **Qg = 103 nC, Qgs1 = 25 nC,
Qgd = 12.4 nC** per FET.

| Term | Value | Derivation |
|---|---:|---|
| Driver propagation delay, INx -> Gx | ~100 ns | DRV8323 t_PD (ESC-009) |
| Gate discharge, plateau -> off | (206 - 50) nC / 1 A = 156 ns | 2 x (Qg - Qgs1) |
| **t_off total** | **~256 ns** | |
| Driver propagation delay (incoming) | ~100 ns | cancels against the above |
| Gate charge, 0 V -> plateau | 50 nC / 300 mA = 167 ns | 2 x Qgs1 |
| **t_on_delay total** | **~267 ns** | |
| **Net requirement** | **-11 ns** | |

**The net requirement comes out negative**, and that is the real result,
not a rounding artefact. Because `IDRIVEN` is set 3.3x higher than
`IDRIVEP`, the outgoing FET is already off before the incoming one starts
to conduct, even with zero inserted dead time. Under nominal conditions
this bridge cannot cross-conduct.

So the 625 ns is not covering a nominal overlap — there isn't one. It is
margin against everything that is *not* nominal:

- V_th spread across twelve individual FETs,
- Q_g and R_DS(on) drift over a 150 C junction swing,
- two paralleled gates not switching in unison,
- gate-loop ringing momentarily re-crossing V_th.

625 ns costs 1.5 % of duty at 24 kHz. Buying that much insurance against
a failure that destroys twelve MOSFETs is an easy trade, which is why the
number is not tuned down aggressively.

### Gate-drive current, from the same datasheet numbers

DRV8323 datasheet SLVSDJ3D Eq. 11/12 sizes `IDRIVE` from the **Miller**
charge, not total gate charge:

```
Qgd(position) = 2 x 12.4 nC = 24.8 nC
IDRIVEP > Qgd / t_rise = 24.8 nC / 100 ns = 248 mA   -> set 300 mA
IDRIVEN > Qgd / t_fall = 24.8 nC /  50 ns = 496 mA   -> set 1 A
```

The 1 A sink setting is deliberately above the 496 mA minimum: it is what
produces the turn-off/turn-on asymmetry the budget above relies on.

> Reduce toward `DEAD_TIME 24` (375 ns) only on the bench, with a current
> probe on the DC bus watching for the characteristic shoot-through spike
> at each commutation, and only after the FET and gate-drive settings are
> final.

---

## Layer 2 — DRV8323R internal cross-conduction prevention

The DRV8323R, in 6x PWM mode, independently refuses to turn on one side
while the other is still commanded on, and inserts its own programmable
dead time of **50 / 100 / 200 / 400 ns**. This is a property of the gate
driver silicon and holds even if the MCU commands an illegal state.

Set to **100 ns**. It is deliberately *shorter* than the TIM1 value so the
total dead time stays the deterministic, documented 625 ns rather than the
sum of two uncoordinated delays — the driver's setting acts as a floor for
the case where layer 1 is wrong, not as an addition to it.

- **RS variant:** `DEAD_TIME` bits in the Driver Control register, over SPI.
- **RH variant:** resistor on the `DTC` pin.

---

## Layer 3 — Discrete cross-interlock (sheet 06)

Six **SN74LVC1G97** configurable single-gate logic parts (SOT-23-6, LCSC
C128411) sit between the MCU and the driver inputs.

The '1G97 is a 3-input configurable gate. Its function table (datasheet
SCES416N, Table 1) is a 2-to-1 mux with `In2` as the select:

```
  In2 = L  ->  Y = In1
  In2 = H  ->  Y = In0          i.e.  Y = /In2.In1 + In2.In0
```

TI documents the tie-off we want directly, as **Figure 6, "2-Input AND Gate
With One Inverted Input"**: ground `In0`, and the part becomes
`Y = In1 AND NOT In2`. So:

| Gate | pin 1 `In1` | pin 3 `In0` | pin 6 `In2` | pin 4 `Y` |
|---|---|---|---|---|
| high side | `INHx` from MCU | **GND** | `INLx` from MCU | `INHx` to driver |
| low side | `INLx` from MCU | **GND** | `INHx` from MCU | `INLx` to driver |

```
  INHx_drv = INHx AND NOT INLx
  INLx_drv = INLx AND NOT INHx
```

Both outputs cannot be high simultaneously for any input combination -- it
is combinational, so there is no state to corrupt. Propagation delay is
6.3 ns max at 3.3 V and **identical on both paths**, so it adds no skew and
does not eat into the dead-time budget.

**Is this redundant with layer 2? Largely, yes — and it is here anyway,
for two cases layer 2 does not cover:**

1. **Before the driver is configured.** Between power-on and the point
   where firmware asserts `ENABLE` and writes the SPI registers, the
   DRV8323R's PWM mode is not yet known to be 6x. The interlock is true
   from the instant 3V3 comes up.
2. **A wrong SPI write.** In 3x or 1x PWM mode the `INLx` pins change
   meaning entirely (direction / brake rather than low-side command). A
   firmware bug that selects the wrong mode would silently invalidate
   layer 2's interlock assumption. Layer 3 does not care what mode the
   driver is in.

Each gate has a **0 Ohm bypass link** in parallel so the interlock can be
shorted out for characterisation.

---

## Layer 4 — Gate network and fail-safe biasing (sheet 03)

- **10 kOhm gate-source pulldown on every one of the 12 FETs.** An
  undriven gate is a floating gate, and a floating gate on a 12 V bus with
  dv/dt on the drain will turn a FET on through C_gd. This is the single
  most important passive on the power sheet, and it is what makes the board
  safe during power-up, brown-out, and driver reset.
- **Individual 4.7 Ohm series gate resistor per FET**, not per position.
  Two gates tied directly together form a resonant loop through their own
  package inductance and will oscillate at hundreds of MHz. Separate
  resistors de-Q that loop. This is mandatory for paralleled FETs.
- **Anti-parallel diode across the common gate resistor** (one per
  position, 6 total) so turn-off bypasses the resistor while turn-on does
  not. Turn-off becomes faster than turn-on, which *widens* the effective
  dead time — the asymmetry is in the safe direction.
- **10 kOhm pulldown on all six `INHx`/`INLx` driver inputs**, so a
  tri-stated or unpowered MCU commands "off" rather than "undefined".

---

## Layer 0 — nFAULT into TIM1_BKIN (the fast path out)

Not dead-time related, but the same class of protection and worth stating
plainly: the DRV8323R's **`nFAULT`** output goes to **PB12**, which carries
**TIM1_BKIN**. When the driver detects VDS overcurrent, charge-pump
undervoltage, gate-drive fault or overtemperature, it pulls `nFAULT` low
and the timer's break input forces all six PWM outputs to their inactive
state **in hardware, within one timer clock**, with no interrupt, no
firmware, and no latency.

Firmware then sees the break flag and decides whether to latch off or
retry. Routing a fault to a GPIO and handling it in an ISR — which is what
most ESC designs do — costs about a microsecond, and a microsecond of
shoot-through at 12 V is already fatal.

This requires `BDTRInitStruct.BreakState = LL_TIM_BREAK_ENABLE` in the
firmware patch; AM32's stock G071 init has it **disabled**
(`LL_TIM_BREAK_DISABLE`). See `firmware/README.md`.

> **ESC-003** (in `pinout.md`) tracks confirming that PB12 actually carries
> TIM1_BKIN on this package. Until that is read out of DS12232, layer 0 is
> designed-in but not proven.

---

## Summary

| Layer | Mechanism | Covers | Independent of |
|---|---|---|---|
| 1 | TIM1 DTG, 625 ns | normal commutation | firmware timing bugs |
| 2 | DRV8323R interlock + 100 ns | illegal MCU commands | MCU entirely |
| 3 | 6x 74LVC1G97 | pre-config window, wrong SPI mode | MCU and driver |
| 4 | Gate pulldowns + series R | power-up, brown-out, dv/dt | everything active |
| 0 | nFAULT -> TIM1_BKIN | overcurrent, UVLO, thermal | firmware latency |
