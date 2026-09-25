# Architecture — 12 V / 100 A All-N-Channel Three-Phase Motor Driver

## What this board is

A single-motor brushless ESC (electronic speed controller) for a high-power
12 V drone motor. Six switch positions, each built from **two paralleled
N-channel MOSFETs** (12 FETs total), driven by a **DRV8323R smart gate
driver** with external FETs, commanded by an **STM32G071** running **AM32**
open-source firmware so the board speaks **DShot150/300/600/1200**.

| Parameter | Value | Notes |
|---|---|---|
| Battery | 3S LiPo, 9.0–12.6 V | nominal 11.1 V |
| Operating range | 6–16 V | driver min 6 V; 4S (16.8 V) tolerated |
| Absolute max (silicon) | 40 V FET / 60 V driver | >3x margin on switch-node ringing |
| Continuous current | **100 A** | ~1.2 kW at 12 V |
| Burst current | **150 A**, 10 s | thermally limited, not silicon limited |
| Bridge | 6 positions x 2 FETs = **12 N-channel** | high side AND low side are NMOS |
| PWM frequency | 24 kHz default, 48 kHz option | set in AM32 target |
| Control input | DShot150/300/600/1200, bidirectional | plus telemetry UART |

## Why all-N-channel, and what makes the high side work

A P-channel high-side switch is the easy way to build a bridge, and it is
the wrong way here: P-channel parts with usable R_DS(on) at these currents
do not exist in a sane package. Both rails are N-channel, which means the
high-side gate has to be driven *above* the battery rail.

The DRV8323R solves this with an on-chip **doubler charge pump** rather than
a bootstrap capacitor. That distinction matters for this application:

- A bootstrap cap must be refreshed by pulling the phase node low, so it
  cannot hold the high-side FET on indefinitely — duty cycle is capped
  somewhere below 100%.
- A charge pump holds the gate up forever, so the DRV8323R **supports 100%
  duty cycle**. At full throttle the high-side FET stays fully enhanced,
  which is exactly the regime "drive it very hard" lives in.

The low side is fed from an on-chip low-side linear regulator (VGLS), so
both rails get a clean ~10 V V_GS independent of battery sag.

## Block diagram

```
 XT90 / 8AWG        ┌──────────────── VBAT (12 V) ─────────────────┐
   +12 V ──┬────────┤                                              │
           │    bulk caps                                          │
          GND   3x 330uF polymer        ┌─────────────────┐        │
                + 24x 10uF MLCC         │   DRV8323R      │        │
                                        │  smart gate drv │        │
  ┌──────────────┐   6x PWM   ┌─────────┤  - charge pump  │        │
  │ STM32G071CBU6│───────────▶│interlock│  - VGLS LDO     │        │
  │   (AM32)     │  INHx/INLx │ 6x AND  │  - dead time    │        │
  │              │◀───nFAULT──┤ (74LVC) │  - VDS OCP      │        │
  │ TIM1 + dead  │            └─────────┤  - 3x CSA       │        │
  │ time + BKIN  │◀──SPI (RS variant)───┤  - 600mA buck   │──3V3───┤
  └──────┬───────┘                      └────┬────────────┘        │
         │  COMP2 BEMF                       │ GHx/SHx/GLx         │
         │  + virtual neutral                ▼                     │
         │                     ┌──────────────────────────┐        │
         └─────────────────────┤  12x NMOS, 2 per switch  │        │
    DShot in (PB4) ────────────┤  40 V, 0.85 mOhm         │        │
                               └──────────┬───────────────┘        │
                                          │ A  B  C                │
                                    0.25 mOhm shunt ───────────────┘
                                          │
                                       ┌──▼──┐
                                       │MOTOR│
                                       └─────┘
```

## Sheet map

| Sheet | Block | Key parts |
|---|---|---|
| 01 | Power input & bulk | XT90 pads, reverse-polarity FET, bulk cap bank, TVS |
| 02 | Gate driver | U201 DRV8323R + charge pump / VGLS / buck passives |
| 03 | Power stage | 12x Q3xx MOSFETs, gate networks, shunt, phase pads |
| 04 | MCU | U401 STM32G071CBU6, SWD, DShot input, telemetry |
| 05 | Sense | BEMF dividers, virtual neutral, VBAT divider, NTC |
| 06 | Protection | 6x interlock gates, nFAULT -> TIM1_BKIN, pulldowns |

## Design decisions and the reasoning

**Two FETs per switch, not three.** Two halves conduction loss versus one
while keeping per-position gate charge at ~206 nC, which the DRV8323R charge
pump can still refresh at 48 kHz with margin (see `power-budget.md`). Three
would push the charge pump to its limit and buy less than the first
doubling did.

**40 V FETs on a 12 V bus.** 3S peaks at 12.6 V, but a hard-switched
150 A bridge rings. Parasitic loop inductance of even 5 nH with a 150 A
edge at 100 ns gives V = L·di/dt = 7.5 V of overshoot on top of the rail,
and real layouts do worse. 40 V leaves the part operating at under a third
of its rating.

**Single low-side shunt, three CSAs wired for it.** All three low-side
sources tie to one node; the shunt sits between that node and PGND. CSA A
reads total bus current for AM32 telemetry, CSA B and C are shorted to
PGND. Per-phase VDS overcurrent still works because SHA/SHB/SHC remain
independent. Three separate shunts would buy per-phase FOC current and cost
three times the shunt dissipation — deferred, not designed out.

**Dual-build gate driver.** DRV8323RS (SPI) and DRV8323RH (resistor) are
the same VQFN-48 7x7 pinout with the config pins repurposed. The board
carries both the resistor network and the SPI routing; assembly picks one.
See `docs/gate-driver-config.md`.
