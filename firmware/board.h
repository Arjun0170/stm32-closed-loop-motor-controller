#ifndef BOARD_H
#define BOARD_H
#include <stdint.h>
void board_init(void);
uint32_t board_encoder_count(void);
void board_set_duty(uint32_t basis_points);
int board_uart_get(void);
void board_uart_put(char ch);
uint32_t board_irq_lock(void);
void board_irq_unlock(uint32_t mask);
void board_timer_ack(void);
#endif
