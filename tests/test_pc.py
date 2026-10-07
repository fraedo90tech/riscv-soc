import random
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, Timer
from cocotb_tools.runner import get_runner

@cocotb.test()
async def pc_works(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    
    """Test that the PC module correctly resets to 0 on reset and updates on clock edges."""
    dut.rst.value = 1
    dut.pc_next.value = 0x12345678
    await FallingEdge(dut.clk)
    await FallingEdge(dut.clk)
    assert int(dut.pc_out.value) == 0, f"pc_out: got {int(dut.pc_out.value):#x}, expected 0"

    """Test that the PC module increases pc_out by 4 on each clock edge when not in reset."""
    dut.rst.value = 0
    for i in range(1, 10):
        expected = int(dut.pc_out.value) + 4
        dut.pc_next.value = expected
        await FallingEdge(dut.clk)
        got = int(dut.pc_out.value)
        assert got == expected, f"step {i}: got {got:#x}, expected {expected:#x}"

    dut.pc_next.value = 0x100
    await FallingEdge(dut.clk)
    assert int(dut.pc_out.value) == 0x100, f"pc_out: got {int(dut.pc_out.value):#x}, expected 0x100"

    dut.rst.value = 1
    dut.pc_next.value = 0x200
    await FallingEdge(dut.clk)
    assert int(dut.pc_out.value) == 0, f"pc_out: got {int(dut.pc_out.value):#x}, expected 0 after reset"


def test_pc():
    root = Path(__file__).resolve().parent.parent
    runner = get_runner("verilator")
    runner.build(
        sources=[root / "rtl" / "pc.sv"],
        hdl_toplevel="pc",
        build_dir=root / "sim_build",
        waves=True,
    )
    runner.test(hdl_toplevel="pc", test_module="test_pc", waves=True)