#include "board.h"
#include "controller.h"
#include <stdbool.h>
static controller_t control;
static volatile uint32_t time_ms;
static volatile bool telemetry_due;
void TIM2_IRQHandler(void)
{
    board_timer_ack();
    time_ms += CONTROL_MS;
    controller_tick(&control, board_encoder_count(), time_ms);
    board_set_duty(control.duty); /* includes zero on the detecting update */
    if (time_ms % 50 == 0) telemetry_due = true;
}
static void text(const char *s) { while (*s) board_uart_put(*s++); }
static void number(uint32_t n)
{
    char buf[10]; unsigned count = 0;
    do { buf[count++] = (char)('0' + n % 10); n /= 10; } while (n);
    while (count) board_uart_put(buf[--count]);
}
static void telemetry(const controller_t *c, uint32_t timestamp)
{
    text("T,"); number(timestamp); text(","); number(c->setpoint);
    text(","); number(c->rpm); text(","); number(c->duty);
    text(","); text(controller_state_name(c->state));
    text(","); text(controller_fault_name(c->fault)); text("\n");
}
int main(void)
{
    char line[64]; unsigned length = 0; bool overflow = false, bad = false;
    controller_init(&control, board_encoder_count());
    board_init();
    text("READY STM32F412 TIM2=10ms UART2 MOTOR_MMIO\n");
    for (;;) {
        int ch = board_uart_get();
        if (ch >= 0 && ch != '\r') {
            if (ch == '\n') {
                line[length] = 0;
                if (overflow) text("ERR oversized command\n");
                else if (bad) text("ERR invalid character\n");
                else {
                    uint32_t mask = board_irq_lock();
                    const char *reply = controller_command(&control, line, time_ms);
                    controller_t snapshot = control;
                    uint32_t timestamp = time_ms;
                    board_set_duty(control.duty);
                    board_irq_unlock(mask);
                    text(reply); text("\n");
                    telemetry(&snapshot, timestamp);
                }
                length = 0; overflow = false; bad = false;
            } else if (ch < 32 || ch > 126) bad = true;
            else if (length < sizeof(line) - 1) line[length++] = (char)ch;
            else overflow = true;
        }
        uint32_t mask = board_irq_lock();
        bool due = telemetry_due;
        telemetry_due = false;
        controller_t snapshot = control;
        uint32_t timestamp = time_ms;
        board_irq_unlock(mask);
        if (due) telemetry(&snapshot, timestamp);
    }
}
