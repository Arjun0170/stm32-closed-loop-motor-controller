#!/usr/bin/env python3
"""Drive the real ARM ELF via Renode UART; assert feedback and actuator trace."""
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"


def renode_binary():
    candidates = [os.environ.get("RENODE"), shutil.which("renode"),
                  str(ROOT / ".tools/renode_1.17.0-portable/renode"),
                  str(Path.home() / "tools/renode_1.17.0-portable/renode")]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("Renode missing: run tools/bootstrap.sh or export RENODE=/path/to/renode")


def run_renode(script, log):
    binary = renode_binary()
    with log.open("w") as out:
        result = subprocess.run([binary, "--disable-gui", "--console", "--plain", "-e",
                                 f"include @{script}"], cwd=ROOT, stdout=out,
                                stderr=subprocess.STDOUT, timeout=180)
    output = log.read_text()
    assert result.returncode == 0, output[-6000:]
    assert not re.search(r"error executing|Error E\d|Unhandled exception|\[ERROR\]|CPU abort", output, re.I), output[-6000:]


def read_telemetry(path):
    text = path.read_text()
    rows = []
    for match in re.finditer(r"^T,(\d+),(\d+),(\d+),(\d+),(\w+),(\w+)$", text, re.M):
        t, sp, rpm, duty, state, fault = match.groups()
        rows.append(dict(time_ms=int(t), setpoint=int(sp), rpm=int(rpm), duty=int(duty),
                         state=state, fault=fault))
    assert rows, "No telemetry from ARM UART"
    return text, rows


def settling_time(telemetry, begin, deadline):
    """A full 300ms hold inside +/-5%, first entry relative to event time."""
    rows = [r for r in telemetry if begin <= r["time_ms"] <= deadline and r["state"] == "RUNNING"]
    for first in rows:
        start = first["time_ms"]
        hold = [r for r in rows if start <= r["time_ms"] <= start + 300]
        if hold and hold[-1]["time_ms"] >= start + 300 and all(1140 <= r["rpm"] <= 1260 for r in hold):
            # A missing telemetry interval must not masquerade as a successful hold.
            assert all(b["time_ms"] - a["time_ms"] <= 50 for a, b in zip(hold, hold[1:]))
            return start - begin
    raise AssertionError(f"No 300ms hold at 1200 +/-5% between {begin} and {deadline}")


def assert_startup(telemetry, plant):
    boot = [r for r in telemetry if r["time_ms"] <= 120]
    assert boot and all(r["duty"] == 0 and r["state"] == "STOPPED" for r in boot)
    assert all(r["duty_bp"] == 0 for r in plant if r["time_us"] < 120000)
    assert any(r["encoder"] > 0 and r["plant_rpm"] > 100 for r in plant if 120000 < r["time_us"] < 1000000), "No motor feedback"
    startup = settling_time(telemetry, 140, 2140)
    assert startup + 300 <= 2000
    return startup


def assert_load_recovery(telemetry, plant):
    load_rows = [r for r in plant if r["kind"] == "load"]
    assert len(load_rows) == 1 and load_rows[0]["load_rpm"] == 600
    before = [r for r in telemetry if 1900 <= r["time_ms"] < 2140]
    after = [r for r in telemetry if 2140 <= r["time_ms"] <= 4140]
    dip = min(r["rpm"] for r in after)
    assert dip < 1140, "Load did not produce the required speed dip"
    baseline = sum(r["duty"] for r in before) / len(before)
    assert max(r["duty"] for r in after) > baseline + 1000, "PI failed to raise duty under load"
    # Start search after speed has actually dipped; old pre-disturbance samples cannot qualify.
    dip_time = next(r["time_ms"] for r in after if r["rpm"] == dip)
    recovery = settling_time(telemetry, dip_time, 4140) + dip_time - 2140
    assert recovery + 300 <= 2000
    return recovery, dip, baseline


def assert_fault_cutoff(telemetry, plant):
    """Cutoff is taken from a zero WRITE at the simulated actuator, never UART."""
    freeze = next(r for r in plant if r["kind"] == "freeze")
    last_advance = freeze["last_advance_us"]
    frozen = [r for r in plant if freeze["time_us"] <= r["time_us"] < 5140000]
    assert all(r["encoder"] == freeze["encoder"] for r in frozen), "Encoder did not freeze"
    cutoff = next(r for r in frozen if r["kind"] == "actuator" and r["duty_bp"] == 0)
    elapsed_ms = (cutoff["time_us"] - last_advance) / 1000
    assert 249 <= elapsed_ms <= 260, f"Actuator cutoff {elapsed_ms:.3f}ms violates 260ms bound"
    assert all(r["duty_bp"] == 0 for r in frozen if r["time_us"] >= cutoff["time_us"])
    assert any(r["fault"] == "NO_MOTION" and r["state"] == "FAULT" for r in telemetry if 4140 <= r["time_ms"] <= 4540)
    # Last measured motor speed may increase while disconnected: the injected fault only freezes feedback.
    assert max(r["plant_rpm"] for r in frozen) > freeze["plant_rpm"]
    return elapsed_ms, cutoff["time_us"] / 1000, last_advance / 1000


def assert_latch_and_restart(text, telemetry, plant):
    assert "ERR fault latched" in text
    assert "OK clear-fault STOPPED" in text
    latched = [r for r in telemetry if 5140 <= r["time_ms"] < 5360]
    assert latched and all(r["state"] == "FAULT" and r["duty"] == 0 for r in latched)
    cleared = [r for r in telemetry if 5380 <= r["time_ms"] < 5560]
    assert cleared and all(r["state"] == "STOPPED" and r["fault"] == "NONE" and r["duty"] == 0 for r in cleared)
    assert all(r["duty_bp"] == 0 for r in plant if 5140000 <= r["time_us"] < 5560000)
    recovery = settling_time(telemetry, 5560, 7560)
    assert recovery + 300 <= 2000
    return recovery


def main():
    BUILD.mkdir(exist_ok=True)
    # Old successful evidence must never satisfy a failing new run.
    for name in ["uart.txt", "plant.csv", "metrics.json"]:
        (BUILD / name).unlink(missing_ok=True)
    script = [f"include @{ROOT / 'renode/boot.resc'}",
              f"sysbus.usart2 CreateFileBackend @{BUILD / 'uart.txt'}"]
    def run(seconds):
        script.append(f'emulation RunFor "{seconds:.6f}"')
    def command(line):
        for ch in line + "\n":
            script.append(f"sysbus.usart2 WriteChar {ord(ch)}")
    run(.1)
    command("status"); run(.02)
    command("setpoint 1200"); run(.02)
    command("start"); run(2.0)  # start at 140ms, load at 2140ms
    script.append("sysbus WriteDoubleWord 0x70000008 600"); run(2.0)
    script.append("sysbus WriteDoubleWord 0x7000000c 1"); run(1.0)  # freeze at 4140ms
    script.append("sysbus WriteDoubleWord 0x7000000c 0")
    command("start"); run(.22)  # rejected at 5140ms
    command("clear-fault"); run(.2)  # clear at 5360ms, dwell stopped until 5560ms
    command("start"); run(2.0)
    command("stop"); run(.1)
    # Actual UART parser checks: bounds, syntax, oversized line, then resynchronization.
    for line in ["setpoint 299", "setpoint 2401", "setpoint 1200junk", "unknown", "x" * 80,
                 "setpoint 300", "setpoint 2400", "status"]:
        command(line); run(.02)
    script.append(f'sysbus.motor SaveTrace "{BUILD / "plant.csv"}"')
    script.append("quit")
    resc = BUILD / "demo.resc"
    resc.write_text("\n".join(script) + "\n")
    run_renode(resc, BUILD / "renode.txt")
    text, telemetry = read_telemetry(BUILD / "uart.txt")
    with (BUILD / "plant.csv").open() as f:
        plant = []
        for row in csv.DictReader(f):
            plant.append({k: v if k == "kind" else float(v) for k, v in row.items()})
    startup = assert_startup(telemetry, plant)
    recovery, dip, baseline = assert_load_recovery(telemetry, plant)
    fault_ms, cutoff_ms, last_advance_ms = assert_fault_cutoff(telemetry, plant)
    restart = assert_latch_and_restart(text, telemetry, plant)
    assert text.count("ERR setpoint range 300..2400") == 3
    assert "ERR unknown command" in text and "ERR oversized command" in text
    assert telemetry[-1]["setpoint"] == 2400 and telemetry[-1]["state"] == "STOPPED"
    # TIM2 cadence evidence from actuator writes (command-induced duplicate timestamps excluded).
    writes = [r["time_us"] for r in plant if r["kind"] == "actuator" and 200000 < r["time_us"] < 2100000]
    intervals = [b-a for a,b in zip(writes, writes[1:])]
    assert intervals and all(9999 <= dt <= 10001 for dt in intervals)
    metrics = dict(target="STM32F412 Cortex-M4F (soft-float firmware)",
                   renode=subprocess.check_output([renode_binary(), "--version"], text=True).strip(),
                   elf_sha256=hashlib.sha256((BUILD / "motor.elf").read_bytes()).hexdigest(),
                   startup_entry_ms=startup, startup_hold_complete_ms=startup+300,
                   load_recovery_entry_ms=recovery, load_hold_complete_ms=recovery+300,
                   load_min_measured_rpm=dip, baseline_duty_percent=baseline/100,
                   fault_cutoff_ms=round(fault_ms, 6), fault_zero_at_ms=cutoff_ms,
                   last_encoder_advance_ms=last_advance_ms, restart_entry_ms=restart,
                   trace_rows=len(plant), telemetry_rows=len(telemetry),
                   control_period_us_min=min(intervals), control_period_us_max=max(intervals))
    (BUILD / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print("PASS: ARM boot, TIM2 10ms, UART, closed-loop startup, load recovery, actuator cutoff, latched fault, explicit restart")
    print(json.dumps(metrics, indent=2))

if __name__ == "__main__":
    main()
