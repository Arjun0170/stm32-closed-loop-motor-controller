#include "controller.h"
#include <string.h>

uint32_t encoder_delta(uint32_t current, uint32_t previous)
{
    /* Unsigned subtraction is defined modulo 2^32. One-direction motion only. */
    return current - previous;
}
void controller_init(controller_t *c, uint32_t count)
{
    memset(c, 0, sizeof(*c));
    c->setpoint = 1200;
    c->previous_count = count;
}
uint32_t pi_update(controller_t *c, int32_t error)
{
    /* Kp=.025 duty-percent/RPM, Ki=.12 duty-percent/(RPM*s), dt=.01s.
       Conditional integration: reject a step driving farther into saturation. */
    int32_t candidate = c->integral + error * 12;
    int32_t proportional = error * 5 / 2;
    int32_t output = proportional + candidate / 100;
    if (!((output > (int32_t)DUTY_MAX && error > 0) ||
          (output < 0 && error < 0))) {
        c->integral = candidate;
    }
    output = proportional + c->integral / 100;
    if (output < 0) return 0;
    if (output > (int32_t)DUTY_MAX) return DUTY_MAX;
    return (uint32_t)output;
}
void controller_tick(controller_t *c, uint32_t count, uint32_t now_ms)
{
    uint32_t delta = encoder_delta(count, c->previous_count);
    c->previous_count = count;
    /* 25 RPM/count per 10ms; five samples give 50ms trailing average. */
    c->window_sum -= c->window[c->window_index];
    c->window[c->window_index] = delta;
    c->window_sum += delta;
    c->window_index = (c->window_index + 1) % 5;
    c->rpm = c->window_sum * 5;
    if (delta || c->state != RUNNING) {
        c->last_motion_ms = now_ms;
    }
    if (c->state != RUNNING) {
        c->integral = 0;
        c->duty = 0;
        return;
    }
    c->duty = pi_update(c, (int32_t)c->setpoint - (int32_t)c->rpm);
    if (c->duty >= 2000 && (uint32_t)(now_ms - c->last_motion_ms) >= NO_MOTION_MS) {
        c->state = FAULT;
        c->fault = NO_MOTION;
        c->integral = 0;
        c->duty = 0;
    }
}
static bool parse_rpm(const char *s, uint32_t *value)
{
    uint32_t v = 0;
    if (!*s) return false;
    while (*s) {
        if (*s < '0' || *s > '9') return false;
        v = v * 10 + (uint32_t)(*s++ - '0');
        if (v > 2400) return false; /* also prevents arithmetic overflow */
    }
    if (v < 300) return false;
    *value = v;
    return true;
}
const char *controller_command(controller_t *c, const char *line, uint32_t now_ms)
{
    uint32_t value;
    if (!strcmp(line, "status")) return "STATUS";
    if (!strncmp(line, "setpoint ", 9)) {
        if (!parse_rpm(line + 9, &value)) return "ERR setpoint range 300..2400";
        c->setpoint = value;
        return "OK setpoint";
    }
    if (!strcmp(line, "start")) {
        if (c->fault != NONE) return "ERR fault latched";
        if (c->state != RUNNING) {
            c->integral = 0;
            c->last_motion_ms = now_ms;
            c->state = RUNNING;
        }
        return "OK start";
    }
    if (!strcmp(line, "stop")) {
        c->duty = 0;
        c->integral = 0;
        if (c->fault == NONE) c->state = STOPPED;
        return "OK stop";
    }
    if (!strcmp(line, "clear-fault")) {
        c->state = STOPPED;
        c->fault = NONE;
        c->duty = 0;
        c->integral = 0;
        c->last_motion_ms = now_ms;
        return "OK clear-fault STOPPED";
    }
    return "ERR unknown command";
}
const char *controller_state_name(motor_state_t s)
{
    return s == RUNNING ? "RUNNING" : s == FAULT ? "FAULT" : "STOPPED";
}
const char *controller_fault_name(fault_t f) { return f == NO_MOTION ? "NO_MOTION" : "NONE"; }
