#ifndef CONTROLLER_H
#define CONTROLLER_H
#include <stdint.h>
#include <stdbool.h>
#define CONTROL_MS 10u
#define COUNTS_PER_REV 240u
#define NO_MOTION_MS 250u
#define DUTY_MAX 10000u
/* Duty is in basis points: 10000 = 100%. All state has one ISR owner. */
typedef enum { STOPPED, RUNNING, FAULT } motor_state_t;
typedef enum { NONE, NO_MOTION } fault_t;
typedef struct {
    motor_state_t state;
    fault_t fault;
    uint32_t setpoint, rpm, duty, previous_count, last_motion_ms;
    uint32_t window[5], window_sum, window_index;
    int32_t integral; /* basis points * 100 */
} controller_t;
void controller_init(controller_t *c, uint32_t count);
uint32_t encoder_delta(uint32_t current, uint32_t previous);
uint32_t pi_update(controller_t *c, int32_t error);
void controller_tick(controller_t *c, uint32_t count, uint32_t now_ms);
const char *controller_command(controller_t *c, const char *line, uint32_t now_ms);
const char *controller_state_name(motor_state_t s);
const char *controller_fault_name(fault_t f);
#endif
