from pathlib import Path
import cocotb
from cocotb.triggers import FallingEdge
from cocotb.clock import Clock
from cocotb_tools.runner import get_runner
@cocotb.test()
async def counter_works(dut):
    """Test that the counter counts up when enabled and resets when rst is high."""
    Clock(dut.clk, 10, unit="ns").start()
    dut.rst.value = 1
    dut.en.value = 0
    await cocotb.triggers.FallingEdge(dut.clk)
    await cocotb.triggers.FallingEdge(dut.clk)
    dut.rst.value = 0
    dut.en.value = 1
    for i in range(20):
        await cocotb.triggers.FallingEdge(dut.clk)
        assert dut.count.value == i + 1, f"Count was {dut.count.value} but expected {i}"

def test_counter():
    root = Path(__file__).resolve().parent.parent
    runner = get_runner("verilator")
    runner.build(
        sources=[root / "rtl" / "counter.sv"],
        hdl_toplevel="counter",
        build_dir=root / "sim_build",
        waves=True,
    )
    runner.test(hdl_toplevel="counter", test_module="test_counter", waves=True)
