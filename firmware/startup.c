#include <stdint.h>
extern uint32_t _estack, _sidata, _sdata, _edata, _sbss, _ebss;
extern int main(void);
void TIM2_IRQHandler(void);
void Default_Handler(void) { for (;;) {} }
void Reset_Handler(void)
{
    uint32_t *source = &_sidata;
    for (uint32_t *dest = &_sdata; dest < &_edata;) *dest++ = *source++;
    for (uint32_t *dest = &_sbss; dest < &_ebss;) *dest++ = 0;
    main();
    for (;;) {}
}
__attribute__((section(".vectors"),used))
void (*const vectors[96])(void) = {
    [0] = (void (*)(void))(&_estack), [1] = Reset_Handler,
    [2] = Default_Handler, [3] = Default_Handler,
    [4] = Default_Handler, [5] = Default_Handler, [6] = Default_Handler,
    [16 + 28] = TIM2_IRQHandler
};
