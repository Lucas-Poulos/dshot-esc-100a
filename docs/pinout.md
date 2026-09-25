# MCU Pinout — STM32G071CBT6 (LQFP-48, 7x7 mm)

## Why this part

AM32 supports the STM32G071. The 48-pin variant is chosen over the more
common 32-pin because it is the only one that frees **PB12 (TIM1_BKIN)**,
which is what makes the hardware fault-break path in `shoot-through.md`
possible, and it leaves a clean SPI bus for the DRV8323RS. It is also
better stocked and *cheaper* than the 32-pin part (LCSC C432212, 3813 in
stock, $2.18 vs C529350 at 424 / $2.54).

Pin numbers below are read from KiCad's own vetted symbol, not transcribed
by hand. KiCad 10 has no `STM32G071CBTx` symbol, but it has
**`STM32G081CBTx`** — the G081CB is the same die and the same package
bonding as the G071CB, differing only by the AES accelerator, and ST
documents both in a single datasheet (**DS12232**). `gen_custom_symbols.py`
copies that symbol into the project library under the correct name.

## AM32 hardware group

`HARDWARE_GROUP_G0_A` + `NO_PA11_PA12_REMAP`.

On the 48-pin package PA9 and PA10 exist as **dedicated** pins 29 and 32,
while pins 33 and 34 are the PA11/PA12 pads that *can* be remapped to
PA9/PA10. AM32 remaps by default (`LL_SYSCFG_EnablePinRemap` in
`Mcu/g071/Src/peripherals.c`), which is right for 28/32-pin parts where
PA9/PA10 are not bonded. Here it is wrong, so the target defines
`NO_PA11_PA12_REMAP` and we wire the dedicated pins 29/32. The shipping
`AIKON_04_G071` target does exactly this, so the path is proven.

## Pin assignment

| Pin | Port | Net | Function |
|---:|---|---|---|
| 1 | PC13 | — | spare |
| 2 | PC14 | — | spare (OSC32_IN) |
| 3 | PC15 | — | spare (OSC32_OUT) |
| 4 | VBAT | +3V3 | tied to VDD |
| 5 | VREF+ | +3V3A | via ferrite + 1 uF \|\| 100 nF |
| 6 | VDD | +3V3 | 100 nF + 4.7 uF |
| 7 | VSS | GND | |
| 8 | PF0 | — | spare |
| 9 | PF1 | — | spare |
| 10 | PF2 | NRST | 100 nF to GND, 10 k pull-up |
| 11 | PA0 | `DRV_nSCS` | SPI chip select (plain GPIO) |
| 12 | PA1 | `ADC_TEMP` | **ADC_IN1** — board temperature |
| 13 | PA2 | `BEMF_C` | **COMP2_INM (IO3)** — phase C back-EMF |
| 14 | PA3 | `V_NEUTRAL` | **COMP2_INP (IO3)** — virtual star point |
| 15 | PA4 | `ADC_BUSV` | **ADC_IN4** — bus voltage divider |
| 16 | PA5 | `LED_DATA` | WS2812 strip (optional) |
| 17 | PA6 | `ADC_CURRENT` | **ADC_IN6** — from DRV8323 SOA |
| 18 | PA7 | `INLC` | **TIM1_CH1N** — phase C low |
| 19 | PB0 | `INLB` | **TIM1_CH2N** — phase B low |
| 20 | PB1 | `INLA` | **TIM1_CH3N** — phase A low |
| 21 | PB2 | `DRV_SDO` | SPI MISO (SPI2_MISO capable) |
| 22 | PB10 | `DRV_SCLK` | SPI SCK (SPI2_SCK capable) |
| 23 | PB11 | `DRV_SDI` | SPI MOSI (SPI2_MOSI capable) |
| 24 | PB12 | `DRV_nFAULT` | **TIM1_BKIN** + EXTI — hardware break |
| 25 | PB13 | `DRV_ENABLE` | GPIO out, 10 k pulldown |
| 26 | PB14 | `DRV_CAL` | GPIO out — CSA auto-calibrate |
| 27 | PB15 | — | spare |
| 28 | PA8 | `INHC` | **TIM1_CH1** — phase C high |
| 29 | PA9 | `INHB` | **TIM1_CH2** — phase B high (dedicated pin) |
| 30 | PC6 | `LED_STATUS` | status LED |
| 31 | PC7 | — | spare |
| 32 | PA10 | `INHA` | **TIM1_CH3** — phase A high (dedicated pin) |
| 33 | PA11 | — | **no connect** (remap disabled) |
| 34 | PA12 | — | **no connect** (remap disabled) |
| 35 | PA13 | `SWDIO` | debug |
| 36 | PA14 | `SWCLK` | debug (also PA14-BOOT0) |
| 37 | PA15 | — | spare |
| 38–41 | PD0–PD3 | — | spare |
| 42 | PB3 | `BEMF_B` | **COMP2_INM (IO1)** — phase B back-EMF |
| 43 | PB4 | `DSHOT_IN` | **TIM3_CH1 + DMA1_CH1** — DShot input |
| 44 | PB5 | — | spare |
| 45 | PB6 | `TELEM` | **USART1 (AF0)** — one-wire telemetry |
| 46 | PB7 | `BEMF_A` | **COMP2_INM (IO2)** — phase A back-EMF |
| 47 | PB8 | — | spare |
| 48 | PB9 | — | spare |

## Sensorless commutation

AM32 runs one comparator (COMP2) and multiplexes its **inverting** input
between the three phase dividers, while the **non-inverting** input sits on
a fixed virtual neutral. Verified against
`Mcu/g071/Src/peripherals.c`, which states the mapping in a comment:

```
PA2   ------> COMP2_INM
PA3   ------> COMP2_INP
```

and `Inc/targets.h`:

```c
#define PHASE_A_COMP LL_COMP_INPUT_MINUS_IO2 // pb7
#define PHASE_B_COMP LL_COMP_INPUT_MINUS_IO1 // pb3
#define PHASE_C_COMP LL_COMP_INPUT_MINUS_IO3 // pa2
```

The virtual neutral is three equal resistors from phase A/B/C tied to a
common node — it synthesises the motor's star point, which is not brought
out on a delta or unterminated wye motor. See sheet 05.

## Open items

> **ESC-002 — SPI alternate-function numbers unverified.** PB10/PB11/PB2
> are the correct *pins* for SPI2 on STM32G0, but the AF index for each
> has not been read out of DS12232 Table 13. This is deliberately not
> load-bearing: AM32 has no SPI driver, so the DRV8323RS configuration
> transfer is **bit-banged** on these pins as plain GPIO. Hardware SPI2 is
> an optimisation to enable later, only after the AF table is checked.

> **ESC-003 — TIM1_BKIN AF on PB12 unverified.** Same situation. The break
> input is a genuine hardware feature and must be confirmed against
> DS12232 before the fault-break path in `shoot-through.md` can be claimed
> as working. If PB12 turns out not to carry TIM1_BKIN, the fallback is
> EXTI on the same pin, which costs interrupt latency (~1 us) instead of
> being instantaneous.
