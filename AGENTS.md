# Documentation and implementation scope

- Write concise, impersonal technical READMEs for a public engineering audience. Cover purpose, architecture, measured results, reproduction, and validation; retain useful links to source functions and test assertions.
- Keep the implementation focused on a one-direction motor, a simple PI controller, fixed-size buffers, and STOPPED/RUNNING/FAULT states. Avoid adding an RTOS or advanced control features without an explicit request.
- Use the virtual motor peripheral for duty commands and encoder counts by design. Label duty as simulated PWM duty; do not add a native PWM/encoder investigation or imply physical hardware validation.
- Keep the real emulated TIM2 interrupt at 10 ms. Validate its cadence through the running ARM firmware and actuator trace. Console handling and telemetry stay outside the interrupt.
- Focus the demo on three events: reaching the target speed, recovering after an applied load, and latching a fault when encoder feedback stops. Retain the explicit clear-fault then start requirement and verify zero actuator duty in between.
- Generate one annotated SVG plot from a successful emulator run. Do not generate PNG plots, fabricate samples, or substitute host controller execution for the ARM ELF.
- Keep the README concise: explain the design, measured results, reproduction commands, and validation. Put deeper reference material in separate documents if needed.
- Preserve reproducible builds, host C tests, emulator integration assertions, captured evidence, and honest limits on what emulation verifies.
