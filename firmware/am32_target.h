/* dshot-esc-100a -- AM32 target definition.
 *
 * Paste into AM32's Inc/targets.h and add DSHOT_ESC_100A to the Makefile
 * target list. See firmware/README.md for the rationale behind each value.
 */

#ifdef DSHOT_ESC_100A
#define FILE_NAME       "DSHOT_ESC_100A"
#define FIRMWARE_NAME   "ESC100A G071"

/* Raw TIM1 BDTR.DTG value, NOT nanoseconds.
 * TIM1 runs at 64 MHz with PSC=0 and CKD=DIV1, so t_DTS = 15.625 ns and
 * DTG <= 127 is linear:  40 * 15.625 ns = 625 ns.
 * Derivation and margin analysis: docs/shoot-through.md            */
#define DEAD_TIME       40

/* 0.25 mOhm shunt (4x 1 mOhm 2512) x 40 V/V DRV8323 CSA gain = 10 mV/A.
 * CSA is configured UNIDIRECTIONAL so zero current reads ~0 V, which is
 * what AM32 expects.                                              */
#define MILLIVOLT_PER_AMP 10
#define CURRENT_OFFSET    0

/* Bus voltage divider: 100k / 10k = 11:1  (verify scaling -- ESC-011) */
#define TARGET_VOLTAGE_DIVIDER 110

/* TIM1 CH1/2/3 + CH1N/2N/3N, COMP2 on PB7/PB3/PA2 with the virtual
 * neutral on PA3, DShot capture on PB4 via TIM3_CH1 + DMA1_CH1.     */
#define HARDWARE_GROUP_G0_A

/* CRITICAL. The 48-pin STM32G071CBT6 bonds PA9 and PA10 to dedicated
 * pins 29 and 32; pins 33/34 are PA11/PA12. AM32 remaps PA11/PA12 onto
 * PA9/PA10 by default, which is correct for 28- and 32-pin packages and
 * WRONG here -- it would drive the three high-side PWM outputs onto pads
 * this board leaves unconnected. Same approach as AIKON_04_G071.     */
#define NO_PA11_PA12_REMAP

/* PA4 = ADC_IN4 (bus voltage), PA6 = ADC_IN6 (current from DRV SOA) */
#define VOLTAGE_ADC_CHANNEL LL_ADC_CHANNEL_4
#define VOLTAGE_ADC_PIN     LL_GPIO_PIN_4
#define CURRENT_ADC_CHANNEL LL_ADC_CHANNEL_6
#define CURRENT_ADC_PIN     LL_GPIO_PIN_6

#define USE_SERIAL_TELEMETRY      /* USART1 one-wire on PB6 */
#define SIXTY_FOUR_KB_MEMORY

/* Configure the DRV8323RS over SPI at boot. Omit for an RH build --
 * that variant is configured entirely by R203-R206.                 */
#define USE_DRV8323

#endif
