#include "board.h"
#define REG32(a) (*(volatile uint32_t *)(a))
#define UART 0x40004400u
#define TIM2 0x40000000u
#define MOTOR 0x70000000u
uint32_t board_irq_lock(void)
{
    uint32_t mask;
    __asm volatile("mrs %0, primask\ncpsid i" : "=r"(mask) :: "memory");
    return mask;
}
void board_irq_unlock(uint32_t mask) { __asm volatile("msr primask, %0" :: "r"(mask) : "memory"); }
uint32_t board_encoder_count(void) { return REG32(MOTOR + 4); }
void board_set_duty(uint32_t basis_points) { REG32(MOTOR) = basis_points; }
void board_timer_ack(void) { REG32(TIM2 + 0x10) = 0; }
int board_uart_get(void)
{
    return (REG32(UART) & (1u << 5)) ? (int)(REG32(UART + 4) & 255) : -1;
}
void board_uart_put(char ch)
{
    while (!(REG32(UART) & (1u << 7))) { }
    REG32(UART + 4) = (uint32_t)(unsigned char)ch;
}
void board_init(void)
{
    REG32(0x40023840) |= (1u << 17) | 1u; /* RCC APB1: USART2 and TIM2 */
    REG32(UART + 8) = 139; /* 16MHz / 115200; model exchanges characters */
    REG32(UART + 12) = (1u << 13) | (1u << 3) | (1u << 2);
    board_set_duty(0);
    REG32(TIM2) = 0;
    REG32(TIM2 + 0x28) = 49; /* modeled 50MHz / 50 = 1MHz */
    REG32(TIM2 + 0x2c) = 10000; /* Renode timer reaches ARR after ARR ticks (exclusive limit). */
    REG32(TIM2 + 0x14) = 1; /* update prescaler */
    board_timer_ack();
    REG32(TIM2 + 0xc) = 1; /* update interrupt */
    REG32(0xe000e100) = 1u << 28; /* NVIC TIM2 IRQ28 */
    REG32(TIM2) = 1;
}
