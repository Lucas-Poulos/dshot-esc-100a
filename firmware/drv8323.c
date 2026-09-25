/* DRV8323RS configuration for dshot-esc-100a.
 *
 * AM32 ships no SPI gate-driver support, so this is additive: drop it in
 * Mcu/g071/Src/ and call drv8323_init() from main() after
 * initCorePeripherals() and before the motor is enabled.
 *
 * SPI is BIT-BANGED, deliberately. This is a one-shot boot transaction
 * with no throughput requirement, and bit-banging removes all dependence
 * on the STM32G0 alternate-function table for PB10/PB11/PB2, which has
 * not been verified against DS12232 (issue ESC-002). Hardware SPI2 stays
 * available later -- the pins were chosen to be SPI2-capable.
 *
 * Frame format (SLVSDJ3D section 8.5.1): 16 bits, MSB first.
 *   bit 15    : 1 = read, 0 = write
 *   bits 14-11: register address
 *   bits 10-0 : data
 * Data is captured on the FALLING edge of SCLK; SDO shifts out on the
 * rising edge. nSCS must go high between frames to latch.
 *
 * Register values are derived in docs/gate-driver-config.md.
 */

#include "main.h"
#include "stm32g0xx_ll_gpio.h"

/* ---- pin map (see docs/pinout.md) ---- */
#define DRV_SCLK_PORT   GPIOB
#define DRV_SCLK_PIN    LL_GPIO_PIN_10
#define DRV_SDI_PORT    GPIOB
#define DRV_SDI_PIN     LL_GPIO_PIN_11
#define DRV_SDO_PORT    GPIOB
#define DRV_SDO_PIN     LL_GPIO_PIN_2
#define DRV_NSCS_PORT   GPIOA
#define DRV_NSCS_PIN    LL_GPIO_PIN_0
#define DRV_EN_PORT     GPIOB
#define DRV_EN_PIN      LL_GPIO_PIN_13

/* ---- register addresses ---- */
#define REG_FAULT1      0x00
#define REG_FAULT2      0x01
#define REG_DRIVER_CTRL 0x02
#define REG_GATE_HS     0x03
#define REG_GATE_LS     0x04
#define REG_OCP_CTRL    0x05
#define REG_CSA_CTRL    0x06

/* ---- values: see docs/gate-driver-config.md for the bit-by-bit tables ---- */
#define VAL_DRIVER_CTRL 0x080u  /* 6x PWM, OTW reported on nFAULT          */
#define VAL_GATE_HS     0x39Cu  /* unlocked, 330 mA source / 1140 mA sink  */
#define VAL_GATE_LS     0x79Cu  /* CBC, TDRIVE 4us, same IDRIVE as HS      */
#define VAL_OCP_CTRL    0x151u  /* 100 ns dead time, retry, 4us, VDS 0.13V */
#define VAL_CSA_CTRL    0x0C3u  /* unidirectional, 40 V/V, SPx input       */

static void drv_delay(void)
{
    /* ~1 us at 64 MHz -- well inside the DRV8323's 100 ns SCLK minimum,
     * and slow enough that trace length is irrelevant. */
    for (volatile int i = 0; i < 16; i++) { __NOP(); }
}

static uint16_t drv8323_transfer(uint16_t frame)
{
    uint16_t in = 0;

    LL_GPIO_ResetOutputPin(DRV_SCLK_PORT, DRV_SCLK_PIN);
    LL_GPIO_ResetOutputPin(DRV_NSCS_PORT, DRV_NSCS_PIN);
    drv_delay();

    for (int bit = 15; bit >= 0; bit--) {
        if (frame & (1u << bit)) {
            LL_GPIO_SetOutputPin(DRV_SDI_PORT, DRV_SDI_PIN);
        } else {
            LL_GPIO_ResetOutputPin(DRV_SDI_PORT, DRV_SDI_PIN);
        }
        drv_delay();

        /* rising edge: DRV shifts SDO out */
        LL_GPIO_SetOutputPin(DRV_SCLK_PORT, DRV_SCLK_PIN);
        drv_delay();

        in <<= 1;
        if (LL_GPIO_IsInputPinSet(DRV_SDO_PORT, DRV_SDO_PIN)) {
            in |= 1u;
        }

        /* falling edge: DRV captures SDI */
        LL_GPIO_ResetOutputPin(DRV_SCLK_PORT, DRV_SCLK_PIN);
        drv_delay();
    }

    LL_GPIO_SetOutputPin(DRV_NSCS_PORT, DRV_NSCS_PIN);
    drv_delay();
    return in & 0x7FFu;
}

static void drv8323_write(uint8_t addr, uint16_t data)
{
    drv8323_transfer((uint16_t)((addr & 0x0Fu) << 11) | (data & 0x7FFu));
}

uint16_t drv8323_read(uint8_t addr)
{
    return drv8323_transfer(0x8000u | (uint16_t)((addr & 0x0Fu) << 11));
}

static void drv8323_gpio_init(void)
{
    LL_GPIO_InitTypeDef io = { 0 };
    LL_IOP_GRP1_EnableClock(LL_IOP_GRP1_PERIPH_GPIOA);
    LL_IOP_GRP1_EnableClock(LL_IOP_GRP1_PERIPH_GPIOB);

    io.Mode = LL_GPIO_MODE_OUTPUT;
    io.Speed = LL_GPIO_SPEED_FREQ_HIGH;
    io.OutputType = LL_GPIO_OUTPUT_PUSHPULL;
    io.Pull = LL_GPIO_PULL_NO;

    io.Pin = DRV_SCLK_PIN;  LL_GPIO_Init(DRV_SCLK_PORT, &io);
    io.Pin = DRV_SDI_PIN;   LL_GPIO_Init(DRV_SDI_PORT, &io);
    io.Pin = DRV_NSCS_PIN;  LL_GPIO_Init(DRV_NSCS_PORT, &io);
    io.Pin = DRV_EN_PIN;    LL_GPIO_Init(DRV_EN_PORT, &io);

    io.Mode = LL_GPIO_MODE_INPUT;
    io.Pull = LL_GPIO_PULL_UP;      /* SDO is open-drain */
    io.Pin = DRV_SDO_PIN;   LL_GPIO_Init(DRV_SDO_PORT, &io);

    LL_GPIO_SetOutputPin(DRV_NSCS_PORT, DRV_NSCS_PIN);   /* idle high */
}

void drv8323_init(void)
{
    drv8323_gpio_init();

    /* ENABLE high brings the device out of sleep. The datasheet requires
     * ~1 ms before the SPI interface is ready; be generous, this runs
     * once at boot. */
    LL_GPIO_SetOutputPin(DRV_EN_PORT, DRV_EN_PIN);
    for (volatile int i = 0; i < 200000; i++) { __NOP(); }

    drv8323_write(REG_DRIVER_CTRL, VAL_DRIVER_CTRL);
    drv8323_write(REG_GATE_HS,     VAL_GATE_HS);
    drv8323_write(REG_GATE_LS,     VAL_GATE_LS);
    drv8323_write(REG_OCP_CTRL,    VAL_OCP_CTRL);
    drv8323_write(REG_CSA_CTRL,    VAL_CSA_CTRL);

    /* Clear any fault latched during power-up. */
    drv8323_write(REG_DRIVER_CTRL, VAL_DRIVER_CTRL | 0x001u);  /* CLR_FLT */
}

/* Read back every control register and compare. Returns 0 on match.
 *
 * Worth calling during bring-up: a DRV8323RH accidentally fitted where an
 * RS was intended will ACK nothing and read back zeros, and this is the
 * cheapest way to find that out -- before a motor is attached. */
int drv8323_verify(void)
{
    static const uint8_t addr[5] = { REG_DRIVER_CTRL, REG_GATE_HS,
                                     REG_GATE_LS, REG_OCP_CTRL,
                                     REG_CSA_CTRL };
    static const uint16_t want[5] = { VAL_DRIVER_CTRL, VAL_GATE_HS,
                                      VAL_GATE_LS, VAL_OCP_CTRL,
                                      VAL_CSA_CTRL };
    int bad = 0;
    for (int i = 0; i < 5; i++) {
        if (drv8323_read(addr[i]) != want[i]) {
            bad++;
        }
    }
    return bad;
}
