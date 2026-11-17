using System;
using System.IO;
using System.Text;
using System.Globalization;
using Antmicro.Renode.Core;
using Antmicro.Renode.Peripherals.Bus;

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    // Analytic zero-order-hold plant. The clock is Renode virtual time, never wall time.
    public class MotorPlant : IDoubleWordPeripheral, IKnownSize
    {
        public MotorPlant(Machine machine) { this.machine = machine; Reset(); }
        public long Size { get { return 0x100; } }
        private double Now { get { return machine.ElapsedVirtualTime.TimeElapsed.TotalSeconds; } }
        public void Reset()
        {
            speed = rotations = time = lastAdvance = 0;
            duty = 0; load = 0; frozen = false; count = 0;
            trace = new StringBuilder("time_us,duty_bp,encoder,plant_rpm,load_rpm,frozen,last_advance_us,kind\n");
        }
        private double Integral(double dt, double target, double initial)
        {
            return target * dt + (initial - target) * 0.2 * (1 - Math.Exp(-dt / 0.2));
        }
        private void Advance()
        {
            double now = Now, dt = now - time;
            if(dt <= 0) return;
            double target = Math.Max(0, 3000.0 * duty / 10000.0 - load);
            double initial = speed;
            speed = target + (initial - target) * Math.Exp(-dt / 0.2);
            if(!frozen)
            {
                double old = rotations;
                rotations += Integral(dt, target, initial) * 4.0; // 240/60 counts per RPM second
                ulong updated = (ulong)Math.Floor(rotations);
                if(updated != count)
                {
                    // Find virtual time of the latest count crossing, not time of UART output.
                    double lo = 0, hi = dt;
                    for(int i = 0; i < 40; i++)
                    {
                        double mid = (lo + hi) / 2;
                        if(old + Integral(mid, target, initial) * 4.0 < updated) lo = mid;
                        else hi = mid;
                    }
                    lastAdvance = time + hi;
                    count = updated;
                }
            }
            time = now;
        }
        private void Record(string kind)
        {
            trace.AppendFormat(CultureInfo.InvariantCulture, "{0:F3},{1},{2},{3:F6},{4},{5},{6:F3},{7}\n",
                Now * 1e6, duty, (uint)count, speed, load, frozen ? 1 : 0, lastAdvance * 1e6, kind);
        }
        public uint ReadDoubleWord(long offset)
        {
            Advance();
            switch(offset)
            {
                case 0: return duty;
                case 4: return (uint)count;
                case 8: return (uint)load;
                case 12: return frozen ? 1u : 0u;
                default: return 0;
            }
        }
        public void WriteDoubleWord(long offset, uint value)
        {
            Advance();
            if(offset == 0) { duty = Math.Min(value, 10000u); Record("actuator"); }
            else if(offset == 8) { load = (int)Math.Min(value, 3000u); Record("load"); }
            else if(offset == 12) { frozen = value != 0; Record(frozen ? "freeze" : "restore"); }
        }
        public void SaveTrace(string path) { Advance(); File.WriteAllText(path, trace.ToString()); }
        private readonly Machine machine;
        private StringBuilder trace;
        private double speed, rotations, time, lastAdvance;
        private uint duty;
        private int load;
        private bool frozen;
        private ulong count;
    }
}
