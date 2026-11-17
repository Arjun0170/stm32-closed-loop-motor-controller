using System;
using System.IO;
using System.Text;
using System.Globalization;
using Antmicro.Renode.Core;
using Antmicro.Renode.Peripherals;
using Antmicro.Renode.Peripherals.Bus;
namespace Antmicro.Renode.Peripherals.Miscellaneous {
 public class NativeTimerProbe : IGPIOReceiver, IDoubleWordPeripheral, IKnownSize {
  public NativeTimerProbe(Machine machine) { this.machine=machine; Reset(); }
  public void Reset() { level=false; trace=new StringBuilder("time_us,level\n"); }
  public void OnGPIO(int number, bool value) {
   level=value;
   trace.AppendFormat(CultureInfo.InvariantCulture,"{0:F3},{1}\n",machine.ElapsedVirtualTime.TimeElapsed.TotalSeconds*1e6,value?1:0);
  }
  public void SaveTrace(string path) { OnGPIO(-1, level); File.WriteAllText(path,trace.ToString()); }
  public uint ReadDoubleWord(long offset) { return 0; }
  public void WriteDoubleWord(long offset,uint value) {}
  public long Size { get { return 0x100; } }
  private bool level; private Machine machine; private StringBuilder trace;
 }
}
