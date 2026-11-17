ARM_GCC ?= $(shell command -v arm-none-eabi-gcc 2>/dev/null || echo $(HOME)/tools/xpack-arm-none-eabi-gcc-15.2.1-1.1/bin/arm-none-eabi-gcc)
HOST_CC ?= cc
PYTHON ?= python3
CFLAGS = -std=c11 -Wall -Wextra -Werror -O2 -g -Ifirmware
ARMFLAGS = -mcpu=cortex-m4 -mthumb -mfloat-abi=soft -ffreestanding -ffunction-sections -fdata-sections
SOURCES = firmware/startup.c firmware/main.c firmware/board.c firmware/controller.c
.PHONY: all host-test integration demo probe clean
all: build/motor.elf
build:
	mkdir -p build
build/motor.elf: $(SOURCES) firmware/controller.h firmware/board.h firmware/linker.ld | build
	$(ARM_GCC) $(CFLAGS) $(ARMFLAGS) $(SOURCES) -nostartfiles --specs=nosys.specs -Wl,-T,firmware/linker.ld,--gc-sections,-Map,build/motor.map -o $@
build/host_tests: tests/test_controller.c firmware/controller.c firmware/controller.h | build
	$(HOST_CC) $(CFLAGS) -fsanitize=undefined,address -fno-omit-frame-pointer tests/test_controller.c firmware/controller.c -o $@
host-test: build/host_tests
	./build/host_tests
integration: all
	$(PYTHON) tests/integration.py
probe:
	$(PYTHON) tests/native_timer_probe.py
demo: integration
	$(PYTHON) tools/plot.py
clean:
	$(PYTHON) -c 'import shutil; shutil.rmtree("build", ignore_errors=True)'
