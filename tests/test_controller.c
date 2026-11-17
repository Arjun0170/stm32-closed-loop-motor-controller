#include "controller.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static void command_bounds(void)
{
    controller_t c; controller_init(&c, 0);
    const char *invalid[] = {"setpoint 299", "setpoint 2401", "setpoint -300", "setpoint +300", "setpoint ", "setpoint 1200x", "setpoint 1200 ", "setpoint 999999999999999999", "bogus", "", "start now"};
    for (unsigned i = 0; i < sizeof(invalid)/sizeof(invalid[0]); i++) {
        assert(!strncmp(controller_command(&c, invalid[i], 0), "ERR", 3));
        assert(c.setpoint == 1200 && c.state == STOPPED && c.duty == 0);
    }
    assert(!strcmp(controller_command(&c, "setpoint 300", 0), "OK setpoint"));
    assert(c.setpoint == 300);
    assert(!strcmp(controller_command(&c, "setpoint 2400", 0), "OK setpoint"));
    assert(c.setpoint == 2400);
    assert(!strcmp(controller_command(&c, "status", 0), "STATUS"));
}
static void wraparound(void)
{
    assert(encoder_delta(3, UINT32_MAX - 2) == 6);
    controller_t c; controller_init(&c, UINT32_MAX - 2);
    controller_tick(&c, 3, 10);
    assert(c.rpm == 30); /* six counts over a zero-filled 50ms window */
    for (uint32_t i=1; i<=5; i++) controller_tick(&c, 3+i*48, 10+i*10);
    assert(c.rpm == 1200);
}
static void saturation(void)
{
    controller_t c; controller_init(&c, 0);
    for (unsigned i=0; i<10000; i++) assert(pi_update(&c, 10000) == DUTY_MAX);
    assert(c.integral == 0); /* no positive windup */
    for (unsigned i=0; i<10000; i++) assert(pi_update(&c, -10000) == 0);
    assert(c.integral == 0); /* no negative windup */
    assert(pi_update(&c, 100) > 0);
    assert(c.integral > 0);
    c.integral = 1000000;
    int32_t saved = c.integral;
    assert(pi_update(&c, -100) < DUTY_MAX && c.integral < saved);
}
static void fault_transitions(void)
{
    controller_t c; controller_init(&c, 0);
    controller_command(&c, "start", 0);
    controller_tick(&c, 0, 10);
    assert(c.duty >= 2000);
    for (uint32_t t=20; t<250; t+=10) {
        controller_tick(&c, 0, t);
        assert(c.state == RUNNING);
    }
    controller_tick(&c, 0, 250);
    assert(c.state == FAULT && c.fault == NO_MOTION && c.duty == 0 && c.integral == 0);
    assert(!strcmp(controller_command(&c, "start", 270), "ERR fault latched"));
    controller_tick(&c, 123, 280); /* restored feedback does not clear latch */
    controller_command(&c, "stop", 280);
    assert(c.state == FAULT);
    controller_command(&c, "clear-fault", 290);
    assert(c.state == STOPPED && c.fault == NONE && c.duty == 0);
    controller_tick(&c, 160, 300);
    assert(c.state == STOPPED && c.duty == 0);
    controller_command(&c, "start", 300);
    controller_tick(&c, 180, 310);
    assert(c.state == RUNNING && c.duty > 0);
    controller_command(&c, "stop", 315);
    assert(c.state == STOPPED && c.integral == 0 && c.duty == 0);
    /* Low duty does not erase elapsed time since the last actual advance. */
    controller_init(&c, 0); controller_command(&c, "setpoint 300", 0);
    controller_command(&c, "start", 0);
    for (uint32_t t=10; t<=300; t+=10) controller_tick(&c, 0, t);
    assert(c.state == RUNNING && c.duty < 2000 && c.last_motion_ms == 0);
    controller_command(&c, "setpoint 2400", 300);
    controller_tick(&c, 0, 310);
    assert(c.state == FAULT && c.duty == 0);
    /* Millisecond rollover and an advancing encoder both preserve fault timing. */
    controller_init(&c, 0); controller_command(&c, "start", UINT32_MAX-100);
    c.duty = 3000; c.last_motion_ms = UINT32_MAX-100;
    controller_tick(&c, 1, UINT32_MAX-20);
    controller_tick(&c, 1, 220);
    assert(c.state == RUNNING);
    controller_tick(&c, 1, 230);
    assert(c.state == FAULT && c.duty == 0);
}
int main(void)
{
    command_bounds(); wraparound(); saturation(); fault_transitions();
    puts("PASS: command bounds, encoder wraparound, PI saturation/anti-windup, fault transitions");
}
