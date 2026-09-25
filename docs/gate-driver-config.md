# DRV8323R Configuration — RH and RS Builds

The board is laid out for **both** DRV8323R variants. They are the same
VQFN-48 RGZ package with the same pinout; per datasheet SLVSDJ3D Table 6-4,
**only pins 29-32 differ**:

| Pin | DRV8323**RH** (hardware) | DRV8323**RS** (SPI) |
|---:|---|---|
| 29 | `MODE` | `SDO` |
| 30 | `IDRIVE` | `SDI` |
| 31 | `VDS` | `SCLK` |
| 32 | `GAIN` | `nSCS` |

| | RH | RS |
|---|---|---|
| LCSC | C543035 | C2653553 |
| Stock / price | 2338 / $2.39 | 67 / $4.29 |
| Configured by | resistors R203-R206 | MCU, over SPI |
| Firmware needed | **none** — stock AM32 runs | `drv8323.c` init (supplied) |
| Retuning | swap resistors | change a constant, reflash |

> **Populate exactly one set.** For an RH build fit R203-R206 and leave the
> MCU's SPI pins as inputs. For an RS build **do not fit R203-R206** — a
> 10 k resistor to ground on a live SPI line is a fight the MCU wins, but
> it corrupts logic levels and wastes current. R207 (SDO pull-up) is fitted
> only for RS; SDO is open-drain.

---

## RS build — register values

Derived from SLVSDJ3D Tables 8-15 through 8-19, and from the FET's own
measured gate charge (see `docs/shoot-through.md`). Implemented in
`firmware/drv8323.c`.

### 0x02 Driver Control — `0x080`

| Field | Bits | Value | Why |
|---|---|---|---|
| `PWM_MODE` | 6-5 | `00b` | **6x PWM** — independent high/low per phase, which is what AM32's TIM1 complementary outputs produce |
| `OTW_REP` | 7 | `1b` | report overtemperature warning on `nFAULT` so the break path sees thermal trouble early |
| `DIS_CPUV` | 9 | `0b` | charge-pump undervoltage fault **enabled** |
| `DIS_GDF` | 8 | `0b` | gate-drive fault **enabled** |

### 0x03 Gate Drive HS — `0x39C`

| Field | Bits | Code | Value |
|---|---|---|---|
| `LOCK` | 10-8 | `011b` | unlocked |
| `IDRIVEP_HS` | 7-4 | `1001b` | **330 mA** source |
| `IDRIVEN_HS` | 3-0 | `1100b` | **1140 mA** sink |

### 0x04 Gate Drive LS — `0x79C`

`CBC = 1b`, `TDRIVE = 11b` (4000 ns peak-current window), and the same
`IDRIVEP_LS = 1001b` / `IDRIVEN_LS = 1100b` as the high side.

**Why sink 3.5x harder than source.** Qgd is 12.4 nC per FET, so 24.8 nC
per position. SLVSDJ3D Eq. 11/12 give `IDRIVEP > Qgd/t_r = 248 mA` for a
100 ns rise and `IDRIVEN > Qgd/t_f = 496 mA` for a 50 ns fall. Setting sink
well above that minimum makes turn-off finish before turn-on starts, which
is what drives the dead-time budget negative under nominal conditions.

### 0x05 OCP Control — `0x151`

| Field | Bits | Code | Value |
|---|---|---|---|
| `TRETRY` | 10 | `0b` | 4 ms retry |
| `DEAD_TIME` | 9-8 | `01b` | **100 ns** — a floor beneath TIM1's 625 ns, not an addition to it |
| `OCP_MODE` | 7-6 | `01b` | automatic retry |
| `OCP_DEG` | 5-4 | `01b` | 4 us deglitch |
| `VDS_LVL` | 3-0 | `0001b` | **0.13 V** |

`VDS_LVL` sizing, per SLVSDJ3D Eq. 17 (`V_DS_OCP > I_max * R_DS(on)max`):

```
R_DS(on) hot   = 0.85 mOhm * 1.5      = 1.28 mOhm   (per FET, 125 C)
R per position = 1.28 / 2             = 0.64 mOhm   (two in parallel)
trip current   = 0.13 V / 0.64 mOhm   = 203 A  hot
                 0.13 V / 0.425 mOhm  = 306 A  cold
```

203 A sits above the 150 A burst rating with margin and still catches a
phase-to-phase short long before the FETs do. Raising it to `0010b`
(0.2 V) would push the hot trip to 312 A, which protects almost nothing.

### 0x06 CSA Control — `0x0C3`

| Field | Bits | Code | Value |
|---|---|---|---|
| `CSA_FET` | 10 | `0b` | positive input is `SPx` |
| `VREF_DIV` | 9 | `0b` | **unidirectional** — see below |
| `LS_REF` | 8 | `0b` | low-side VDS measured `SHx` to `SPx` |
| `CSA_GAIN` | 7-6 | `11b` | **40 V/V** |
| `SEN_LVL` | 1-0 | `11b` | 1 V (effectively unused, see below) |

**Unidirectional, not bidirectional.** The default `VREF_DIV = 1b` puts
zero current at VREF/2 = 1.65 V, and AM32 expects a sensor that reads ~0 V
at zero current (`CURRENT_OFFSET` is in millivolts and every shipping
target sets it near 0). Unidirectional also doubles the usable span. The
cost is that regenerative/braking current is no longer measurable —
acceptable for telemetry, and the reason per-phase FOC is listed as a
future change rather than a present capability.

**Scaling with 40 V/V:**

```
R_shunt = 0.25 mOhm  ->  10 mV/A at the ADC
   100 A -> 1.00 V        150 A -> 1.50 V
linear range 0.25 V .. VREF-0.25 V = 3.05 V  ->  saturates at ~305 A
```

So AM32 gets `MILLIVOLT_PER_AMP 10`.

`SEN_LVL` (the shunt overcurrent comparator) would need 1 V across
0.25 mOhm — 4000 A. It can never trip and is left at its default; VDS
overcurrent is the protection that actually does the work here.

---

## RH build — resistor values

`IDRIVE`, `VDS`, `MODE` and `GAIN` are multi-level inputs: the pin is read
as one of 4 or 7 levels set by a resistor to GND (or a tie to GND/VCC).
**The level tables live in SLVSDJ3D Section 8.5 and have not yet been
transcribed** — see issue **ESC-010**. Populating R203-R206 at the
placeholder 10 k shown on sheet 02 will *not* give the settings tabulated
above.

Targets to hit, once the tables are read:

| Pin | Target |
|---|---|
| `MODE` | 6x PWM |
| `IDRIVE` | ~330 mA source / ~1140 mA sink |
| `VDS` | 0.13 V |
| `GAIN` | 40 V/V |

Note the RH part cannot set source and sink independently — one `IDRIVE`
pin sets both. The asymmetry the dead-time budget relies on is therefore
**an RS-only property**. An RH build still has 625 ns of TIM1 dead time
plus the driver's own 100 ns plus the discrete interlock, so it is safe;
it just has less margin than the RS build. This is the strongest technical
argument for populating RS.
