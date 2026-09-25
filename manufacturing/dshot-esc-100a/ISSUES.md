# Board Issues — dshot-esc-100a

Open items. Each one is something that is **assumed rather than verified**,
or a decision deliberately deferred. Nothing here is a known-bad design;
they are the places where a second pass is required before fabrication.

Status: `OPEN` | `RESOLVED` | `WONTFIX`

---

## ESC-001 — Input ripple current budget is not closed  ·  OPEN  ·  high

A three-phase inverter's input ripple peaks near `0.5 × I_dc` RMS, so
**~50 A RMS at 100 A**. The on-board bank covers:

- 3 × 330 µF polymer @ ~2.8 A ripple each = **8.4 A**
- 24 × 10 µF X7R 1210 @ ~1.5-2 A each = **36-48 A**

Two things are unverified. First, the MLCC ripple figure is a rule of
thumb, not a vendor number. Second, a 10 µF 25 V X7R 1210 typically
derates to 5-6 µF at 12 V DC bias, so the array's *effective* capacitance
is roughly half its nameplate.

**Action:** pull vendor DC-bias and ripple curves for the exact MPNs
(C77100 / C160677) and recompute. Regardless of outcome, the mitigation
every ESC in this class uses is a **low-ESR capacitor at the battery
connector on short leads** — lead inductance dominates, not the on-board
bank. Document it as a required accessory.

## ESC-002 — SPI alternate-function numbers unverified  ·  OPEN  ·  low

PB10/PB11/PB2 are the correct *pins* for SPI2 on STM32G0, but the AF index
for each has not been read out of DS12232 Table 13.

**Mitigated by design:** `firmware/drv8323.c` bit-bangs SPI as plain GPIO,
so nothing depends on the AF table. Hardware SPI2 is an optimisation to
enable only after the table is checked.

## ESC-003 — TIM1_BKIN on PB12 unverified  ·  OPEN  ·  medium

The hardware fault-break path (`nFAULT` → `TIM1_BKIN` → all six outputs
forced inactive with no firmware involved) assumes PB12 carries TIM1_BKIN
on this package. Not yet confirmed against DS12232.

**Fallback if wrong:** EXTI on the same pin. Costs ~1 µs of interrupt
latency instead of being instantaneous. The board is still protected by
dead-time layers 1-4; only layer 0 degrades.

## ESC-004 — High-current terminals use a placeholder footprint  ·  OPEN  ·  high

`J101`, `J102`, `J301-J303` currently carry
`Connector_Wire:SolderWire-2.5sqmm_1x01_D2.4mm_OD3.6mm_Relief`. **2.5 mm²
is ~14 AWG, good for ~25 A** — nowhere near the 100 A these terminals
carry.

**Action:** draw a custom land pattern for the PCB pass — a large tinned
copper area (~10 × 8 mm, mask-free) per terminal for direct 8 AWG wire
soldering, which is standard ESC practice. Blocks the PCB pass.

## ESC-005 — Shunt Kelvin connection not yet expressed  ·  OPEN  ·  medium

`SPA`/`SNA` connect to the shunt node by name. At 0.25 mΩ, a few
milliohms of trace resistance in the sense path is a large fractional
error, so the sense pins must tap the shunt pads directly as a Kelvin
connection rather than joining the power pour.

Schematic-level nets are correct; this is a **layout constraint** to
encode in the design rules. Blocks the PCB pass, not the schematic.

## ESC-006 — No reverse-polarity protection  ·  OPEN  ·  by design

Deliberately omitted. An ideal-diode FET stage at 100 A adds ~0.5 mΩ
(~5 W) plus its own gate drive and a second failure mode. Mitigation is
the polarised XT90 connector.

**Revisit if** this board is ever used somewhere the connector cannot be
relied on.

## ESC-007 — Buck feedback divider unverified  ·  OPEN  ·  medium

`R201`/`R202` = 33.2 k / 10 k assumes a 0.765 V feedback reference,
giving `0.765 × (1 + 3.32) = 3.30 V`. The DRV8323R's integrated buck is an
LMR16006X, but the reference voltage has not been read out of SNVSA13. The
33 µH inductor and 10 µF output cap are likewise from the general LMR16006
application, not a worked calculation for this operating point.

**Consequence if wrong:** the 3V3 rail is off-target and the MCU may sit
outside 1.71-3.6 V. Check before first power-on.

## ESC-008 — VREF+ has no ferrite  ·  OPEN  ·  low

`U401` pin 5 (`VREF+`) ties straight to 3V3 with 1 µF ‖ 100 nF. Good
practice on a board switching 100 A is a ferrite bead between 3V3 and
VREF+. The ADC reads bus voltage, current and temperature — all slow — so
the impact is small, but it is nearly free to add.

## ESC-009 — DRV8323 propagation delay assumed  ·  OPEN  ·  low

The dead-time budget uses `t_PD ≈ 100 ns` for INx → GHx/GLx. Not yet read
from SLVSDJ3D §7.5. It **cancels to first order** between the turn-on and
turn-off paths, so the budget is insensitive to it; this is tidiness.

## ESC-010 — RH resistor values not transcribed  ·  OPEN  ·  medium

`R203-R206` are placeholder 10 k. The real values come from the 4- and
7-level input tables in SLVSDJ3D §8.5, which have not been transcribed.
**An RH build populated as-drawn will not have the intended IDRIVE, VDS,
MODE or GAIN settings.**

Blocks an RH build only. An RS build ignores these (they are DNP) and is
fully specified in `docs/gate-driver-config.md`.

## ESC-011 — `TARGET_VOLTAGE_DIVIDER` scaling unverified  ·  OPEN  ·  low

Set to 110 for the 100 k / 10 k (11:1) divider, on the assumption that
AM32's constant is `ratio × 10`. Shipping targets use 110 and 210, which
is consistent, but the formula has not been read out of AM32's ADC code.

**Consequence if wrong:** reported battery voltage is scaled wrong, and
low-voltage cutoff triggers at the wrong point. Cosmetic on the bench,
potentially damaging to a LiPo in flight.

## ESC-012 — Thermal design is stated, not simulated  ·  OPEN  ·  medium

`docs/power-budget.md` puts ~19 W at 100 A continuous into roughly
50 × 35 mm of 4-layer 2 oz board — about 1.1 W/cm². That is explicitly
**not passively coolable**; the design assumes propwash or forced air.

No thermal simulation has been run and no copper area has been sized. The
150 A figure is a 10-second burst bounded by thermal mass, not a steady
state. Blocks the PCB pass.
