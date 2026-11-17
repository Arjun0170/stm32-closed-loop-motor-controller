#!/usr/bin/env python3
"""Reproduce the pinned native-timer limitation; this probe does not run firmware.
The application integration test separately runs the ARM ELF and TIM2 IRQ.
"""
import csv
import re
from integration import ROOT, BUILD, run_renode

def main():
    BUILD.mkdir(exist_ok=True)
    out = BUILD / "native-pwm.csv"
    out.unlink(missing_ok=True)
    commands = ["include @renode/NativeTimerProbe.cs", 'mach create "native-timer-probe"',
                "machine LoadPlatformDescription @platforms/cpus/stm32f412.repl",
                "machine LoadPlatformDescription @renode/native-probe.repl",
                "sysbus.cpu IsHalted true"]
    # TIM3_CH1: 1kHz, 50% duty. Then change only CCR1 to zero at 4ms.
    for off, val in [(0, 0), (0x28, 49), (0x2c, 1000), (0x18, 0x60),
                     (0x20, 1), (0x34, 500), (0x14, 1), (0, 1)]:
        commands.append(f"sysbus WriteDoubleWord {0x40000400+off:#x} {val:#x}")
    commands += ['emulation RunFor "0.004"', 'sysbus WriteDoubleWord 0x40000434 0',
                 'emulation RunFor "0.004"', f'sysbus.probe SaveTrace "{out}"']
    # TIM4 encoder mode 3: four quadrature transitions must produce four counts.
    for off, val in [(0, 0), (0x2c, 65535), (0x18, 0x101), (0x20, 0x11), (8, 3), (0, 1)]:
        commands.append(f"sysbus WriteDoubleWord {0x40000800+off:#x} {val:#x}")
    for channel, val in [(0, 'true'), (1, 'true'), (0, 'false'), (1, 'false')]:
        commands.append(f"sysbus.timer4 OnGPIO {channel} {val}")
    commands += ["sysbus ReadDoubleWord 0x40000824", "quit"]
    script = BUILD / "native-probe.resc"
    script.write_text("\n".join(commands) + "\n")
    log = BUILD / "native-probe.txt"
    run_renode(script, log)
    assert re.search(r"0x00000004", log.read_text()), "Encoder probe did not count four transitions"
    with out.open() as f:
        rows = [(float(r["time_us"]), int(r["level"])) for r in csv.DictReader(f)]
    assert (1000, 1) in rows and (1500, 0) in rows and (2500, 0) in rows
    assert rows[-1] == (8000, 1), rows
    assert not any(t > 4000 and level == 0 for t, level in rows)
    print("CONFIRMED Renode 1.17.0 limitation: TIM3 50% PWM works, CCR1=0 at 4ms leaves pin HIGH through 8ms.")
    print("TIM4 native encoder mode counted 4 quadrature transitions; application uses MMIO for safe zero duty.")

if __name__ == "__main__":
    main()
