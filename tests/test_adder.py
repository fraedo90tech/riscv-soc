from pathlib import Path
import cocotb
from cocotb.triggers import Timer
from cocotb_tools.runner import get_runner
@cocotb.test()
async def adder_works(dut):
    """Try every pair of 4-bit numbers and check the sum."""
    for a in range(16):
        for b in range(16):
            dut.a.value = a
            dut.b.value = b
            await Timer(1, unit="ns")
            assert dut.sum.value == a + b, f"{a} + {b} gave {int(dut.sum.value)}"
def test_adder():
    root = Path(__file__).resolve().parent.parent
    runner = get_runner("verilator")
    runner.build(
        sources=[root / "rtl" / "adder.sv"],
        hdl_toplevel="adder",
        build_dir=root / "sim_build",
        waves=True,
    )
    runner.test(hdl_toplevel="adder", test_module="test_adder", waves=True)
