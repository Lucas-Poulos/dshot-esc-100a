# Power Budget and Thermal Analysis

All numbers are for the worst case the board is specified to: **100 A
continuous, 12.6 V bus, 24 kHz PWM, 120-degree trapezoidal commutation**,
which is what AM32 does. Burst figures use 150 A.

Every calculation here is reproducible with `scripts/calc_power.py`.

## 1. Conduction loss

In 6-step drive two phases conduct and one floats at any instant. Each
switch position therefore conducts for 120 degrees of the 360-degree
electrical cycle — a duty of 1/3 — and carries the full phase current while
it does.

```
I_rms(per position) = I_phase * sqrt(1/3) = 100 * 0.5774 = 57.7 A
I_rms(per FET)      = 57.7 / 2            = 28.9 A      (2 in parallel)
```

R_DS(on) rises with junction temperature. The selected FET is 0.85 mOhm max
at V_GS = 10 V, 25 C; the normalised curve gives roughly 1.5x at 125 C:

```
R_hot        = 0.85 mOhm * 1.5 = 1.28 mOhm
P_cond/FET   = 28.9^2 * 1.28e-3 = 1.07 W
P_cond total = 1.07 * 12         = 12.8 W
```

At 150 A burst this scales as I^2: **28.8 W**.

## 2. Switching loss

AM32 PWMs the high-side switch and runs synchronous rectification on the
low side, so one hard transition pair per PWM period per active position.

```
E_sw  = 0.5 * V_bus * I * (t_r + t_f)
      = 0.5 * 12.6 * 100 * (100ns + 100ns)  = 126 uJ
P_sw  = 126e-6 * 24e3                        = 3.0 W   @ 24 kHz
                                             = 6.0 W   @ 48 kHz
```

This is the number that moves most with the IDRIVE setting — faster edges
cut it, at the cost of more ringing and EMI. It is the main reason the
gate drive strength is made adjustable rather than fixed.

## 3. Shunt loss

```
R_shunt = 0.25 mOhm  (4x 1 mOhm 2512 in parallel, 4 W total rating)
P_shunt = 100^2 * 0.25e-3 = 2.5 W     @ 100 A
        = 150^2 * 0.25e-3 = 5.6 W     @ 150 A
```

Four 2512 parts in parallel spread this over ~50 mm^2 of copper. The shunt
is the single hottest discrete component on the board and wants its own
copper pour on both outer layers.

## 4. Gate drive loss

```
Q_g(per position) = 103 nC * 2 = 206 nC
P_gate = Q_g * V_gs * f_pwm * 6 positions
       = 206e-9 * 10 * 24e3 * 6 = 0.30 W
```

Negligible thermally, but it sets the charge pump requirement below.

## 5. Total and thermal

| Source | 100 A cont | 150 A burst |
|---|---:|---:|
| Conduction (12 FETs) | 12.8 W | 28.8 W |
| Switching @24 kHz | 3.0 W | 4.5 W |
| Shunt | 2.5 W | 5.6 W |
| Gate drive | 0.3 W | 0.3 W |
| Driver + MCU + buck | ~0.6 W | ~0.6 W |
| **Total** | **~19 W** | **~40 W** |

19 W into a 4-layer 2 oz board of roughly 50 x 35 mm is about 1.1 W/cm^2.
That is **not** passively coolable at sane temperatures — this board
assumes propwash or forced air, which is the normal condition for an ESC
mounted on a multirotor. Static bench testing at 100 A needs a fan.

The 150 A figure is explicitly a **10-second burst**: 40 W into the same
copper will climb roughly 40 C above the continuous steady state, so it is
bounded by thermal mass, not by dissipation.

## 6. Charge pump headroom (the constraint on paralleling FETs)

DRV8323 datasheet SLVSDJ3D Eq. 9, trapezoidal commutation:

```
I_VCP  >  Q_g * f_PWM
```

`I_VCP` is at least 15 mA at V_VM = 8 V and higher at 12 V. With two FETs
per position:

```
required @ 24 kHz = 206e-9 * 24e3 =  4.9 mA    -> 3.0x margin
required @ 48 kHz = 206e-9 * 48e3 =  9.9 mA    -> 1.5x margin
```

**This is why the design stops at two FETs per position.** A third would
need 14.8 mA at 48 kHz, leaving effectively no margin against the 15 mA
floor, and the failure mode is not graceful — an under-refreshed high-side
gate comes out of full enhancement and the FET cooks.

## 7. Bulk capacitance

Input ripple current for a three-phase inverter peaks near 50% modulation
at roughly `0.5 * I_dc` RMS, so **~50 A RMS at 100 A** — far beyond any
single part.

| Part | Qty | Role |
|---|---:|---|
| 330 uF 25 V polymer, ~4 A ripple | 3 | bulk, ~12 A ripple total |
| 10 uF 25 V X7R 1210 | 24 | distributed across the bridge, ~1.5 A each |
| 100 nF 50 V X7R 0603 | 6 | one per half-bridge, high-frequency loop |

> **Open item ESC-001.** The polymer bank covers ~12 A of the ~50 A ripple
> budget; the MLCC array is doing most of the work and its effective
> capacitance under DC bias must be verified against vendor curves (a
> 10 uF 25 V X7R 1210 typically derates to 5-6 uF at 12 V). The practical
> mitigation used by every ESC in this class is a **low-ESR capacitor at
> the battery connector on short leads**, because lead inductance, not the
> on-board bank, dominates. Document it as a required accessory rather
> than pretending the board alone handles it.

See DRV8323 datasheet section 10.2 "Bulk Capacitance Sizing".
