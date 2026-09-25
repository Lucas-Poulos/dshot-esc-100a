# Firmware — AM32 on this board

This board runs [AM32](https://github.com/am32-firmware/AM32), which is what
makes it DShot-compatible: DShot150/300/600/1200, bidirectional DShot,
and ESC telemetry, all already implemented and field-proven.

Two things are needed on top of stock AM32:

1. **A target definition** (`am32_target.h`) — mechanical, just constants.
2. **A DRV8323RS SPI init** (`drv8323.c`) — AM32 has no SPI gate-driver
   driver at all. Only needed for the **RS** build; an **RH** build runs
   stock AM32 unmodified.

## 1. Target definition

Add the block in `am32_target.h` to AM32's `Inc/targets.h`, and add
`DSHOT_ESC_100A` to the Makefile target list.

Key choices and why:

| Define | Value | Reason |
|---|---|---|
| `HARDWARE_GROUP_G0_A` | — | matches this board's TIM1/COMP2/TIM3 pin map exactly |
| `NO_PA11_PA12_REMAP` | set | **critical.** On the 48-pin G071, PA9/PA10 are dedicated pins 29/32. AM32 remaps PA11/PA12 onto them by default, which is right for 28/32-pin parts and wrong here. Without this the three high-side PWM outputs drive unbonded pads and the motor never spins. The shipping `AIKON_04_G071` target does the same thing. |
| `DEAD_TIME 40` | 625 ns | raw TIM1 `BDTR.DTG`, not nanoseconds. Derived in `docs/shoot-through.md`. |
| `MILLIVOLT_PER_AMP 10` | — | 0.25 mOhm shunt x 40 V/V CSA gain |
| `TARGET_VOLTAGE_DIVIDER 110` | — | 100 k / 10 k = 11:1 (see ESC-011) |

## 2. DRV8323RS SPI init

`drv8323.c` writes the five control registers derived in
`docs/gate-driver-config.md`. It **bit-bangs** SPI rather than using SPI2.

That is a deliberate choice, not a shortcut:

- It is a one-shot transaction at boot plus optional fault polling. There
  is no throughput requirement whatsoever.
- It removes all dependence on the STM32G0 alternate-function table for
  PB10/PB11/PB2, which has **not** been verified against DS12232 (ESC-002).
  Wrong AF number costs a board spin; bit-banging cannot be wrong.
- AM32 has no SPI infrastructure, so hardware SPI would mean adding clock
  enables and init to shared code for zero benefit.

Hardware SPI2 stays available as a later optimisation — the pins were
chosen to be SPI2-capable.

### Call site

In `Src/main.c`, after `initCorePeripherals()` and before the motor is
enabled:

```c
#ifdef USE_DRV8323
    drv8323_init();
#endif
```

### Fault handling

`nFAULT` lands on **PB12 / TIM1_BKIN**. To get the hardware break path,
change AM32's `MX_TIM1_Init()`:

```c
    TIM_BDTRInitStruct.BreakState    = LL_TIM_BREAK_ENABLE;   /* was DISABLE */
    TIM_BDTRInitStruct.BreakPolarity = LL_TIM_BREAK_POLARITY_LOW;
```

With break enabled, a driver fault forces all six outputs inactive in
hardware within one timer clock, with no interrupt and no firmware in the
path. Handling `nFAULT` as a GPIO interrupt instead — which is what most
ESC designs do — costs roughly a microsecond, and a microsecond of
shoot-through at 12 V has already destroyed the bridge.

> This depends on PB12 actually carrying TIM1_BKIN on this package, which
> is **ESC-003 and still unverified**. Until it is confirmed, treat the
> break path as designed-in but unproven, and keep an EXTI fallback.

## Flashing

SWD on `J401` (2x05, 1.27 mm, ARM Cortex Debug pinout) with an ST-LINK:

```bash
# 1. bootloader (once per board)
#    pick the G071 bootloader whose input pin is PB4
# 2. main firmware
make DSHOT_ESC_100A
```

After the bootloader is in, further updates go over the signal wire from a
Betaflight FC or a one-wire USB-serial adapter — no ST-LINK needed.

## Bring-up order

Do not put a motor on this board first.

1. No FETs populated. Confirm 3V3 from the buck, confirm SWD, flash.
2. Still no FETs. Scope `INHx`/`INLx` at the **driver side** of the
   interlock and confirm no overlap, at low and high throttle.
3. Populate FETs. Bench supply **current-limited to 2 A**, no motor.
   Command low throttle; the supply current should stay in the mA range.
   Any jump to the limit is shoot-through — stop.
4. Small motor, no propeller, current-limited supply.
5. Only then the real motor, and only then a propeller.
