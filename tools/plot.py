#!/usr/bin/env python3
"""Plot only evidence emitted by a passing Renode integration run."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from integration import read_telemetry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", action="store_true", help="copy verified trace, metrics and plot into docs/evidence")
    args = parser.parse_args()
    build = ROOT / "build"
    metrics = json.loads((build / "metrics.json").read_text())
    assert metrics["elf_sha256"] == hashlib.sha256((build / "motor.elf").read_bytes()).hexdigest(), "ELF changed: rerun make demo"
    _, uart = read_telemetry(build / "uart.txt")
    with (build / "plant.csv").open() as f:
        plant = list(csv.DictReader(f))
    actual = [p for p in plant if p["kind"] == "actuator"]
    t = [float(p["time_us"]) / 1e6 for p in actual]
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                        "svg.hashsalt": "motor-controller-evidence"})
    fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [2, 1.4, .8]})
    fig.suptitle("STM32F412 closed-loop control | actual ARM execution in Renode 1.17.0", fontsize=15, weight="bold")
    axes[0].axhspan(1140, 1260, color="#2a9d8f", alpha=.13, label="1200 RPM ±5% acceptance band")
    axes[0].plot(t, [float(p["plant_rpm"]) for p in actual], color="#888888", ls="--", label="virtual motor physical speed")
    axes[0].plot([r["time_ms"] / 1000 for r in uart], [r["rpm"] for r in uart], color="#0066b3", lw=1.9, label="firmware encoder estimate (UART)")
    axes[0].set_ylabel("Speed (RPM)")
    axes[0].legend(loc="upper right", fontsize=8)
    axes[1].step(t, [float(p["duty_bp"]) / 100 for p in actual], where="post", color="#c55a11", label="simulated PWM duty at actuator input")
    axes[1].set_ylabel("Duty (%)")
    axes[1].set_ylim(-4, 105)
    axes[1].legend(loc="upper left", fontsize=8)
    values = {"STOPPED": 0, "RUNNING": 1, "FAULT": 2}
    axes[2].step([r["time_ms"] / 1000 for r in uart], [values[r["state"]] for r in uart], where="post", color="#6f42a5", lw=2)
    axes[2].set_yticks([0, 1, 2], ["STOPPED", "RUNNING", "FAULT"])
    axes[2].set_ylim(-.3, 2.4)
    axes[2].set_xlabel("Renode virtual time (s)")
    cutoff = metrics["fault_zero_at_ms"] / 1000
    for ax in axes:
        ax.axvspan(4.14, 5.14, color="#c43b3b", alpha=.08)
        for event in [.14, 2.14, 4.14, cutoff, 5.36, 5.56]:
            ax.axvline(event, color="#bbbbbb", lw=.7, ls=":")
        ax.grid(axis="y", alpha=.2)
        ax.set_xlim(0, 7.66)
    axes[0].annotate("start", xy=(.14, 0), xytext=(.3, 460), arrowprops={"arrowstyle": "->"})
    axes[0].annotate(f'+{metrics["load_rpm"]} RPM opposing load', xy=(2.28, 1020), xytext=(1.35, 2000), arrowprops={"arrowstyle": "->"})
    axes[0].annotate("freeze encoder only", xy=(4.14, 1200), xytext=(3.1, 2050), arrowprops={"arrowstyle": "->"})
    axes[1].annotate(f'NO_MOTION → duty 0\n{metrics["fault_cutoff_ms"]:.3f} ms after last count',
                     xy=(cutoff, 0), xytext=(4.65, 65), arrowprops={"arrowstyle": "->", "color": "#c43b3b"}, color="#a32727")
    axes[2].annotate("clear → STOPPED", xy=(5.36, 0), xytext=(4.6, .5), fontsize=8)
    axes[2].annotate("explicit restart", xy=(5.56, 1), xytext=(5.8, 1.6), fontsize=8)
    fig.text(.5, .016, f'Startup: {metrics["startup_entry_ms"]} ms | load recovery: {metrics["load_recovery_entry_ms"]} ms | each followed by a verified 300 ms hold', ha="center", fontsize=10)
    fig.tight_layout(rect=[0, .04, 1, .96])
    fig.savefig(build / "demo.svg", metadata={"Date": None})
    plt.close(fig)
    if args.snapshot:
        evidence = ROOT / "docs/evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        names = ["demo.svg", "plant.csv", "uart.txt", "metrics.json"]
        for name in names:
            shutil.copyfile(build / name, evidence / name)
        manifest = {name: hashlib.sha256((evidence / name).read_bytes()).hexdigest() for name in names}
        (evidence / "sha256.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print("Captured successful-run evidence in docs/evidence (ELF hash in metrics.json)")
    print("Plot: build/demo.svg")

if __name__ == "__main__":
    main()
