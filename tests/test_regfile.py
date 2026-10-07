import random
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, Timer
from cocotb_tools.runner import get_runner


async def write(dut, addr, data, we=1):
    """Set up a write, let one rising edge happen, then turn we off again."""
    dut.we.value = we
    dut.rd_addr.value = addr
    dut.rd_data.value = data
    await FallingEdge(dut.clk)      # the rising edge in between does the write
    dut.we.value = 0


async def read(dut, addr1, addr2):
    """Read two registers at once (reads need no clock, just a moment to settle)."""
    dut.rs1_addr.value = addr1
    dut.rs2_addr.value = addr2
    await Timer(1, unit="ns")
    return int(dut.rs1_data.value), int(dut.rs2_data.value)


@cocotb.test()
async def regfile_works(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.we.value = 0                 # make sure nothing is written by accident
    await FallingEdge(dut.clk)

    # 1. x0 reads as 0 from the start
    r1, r2 = await read(dut, 0, 0)
    assert r1 == 0 and r2 == 0, f"x0 got {r1:#x} and {r2:#x}, both should read 0"

    # 2. Write a different value to every register 1-31, then read them all back
    values = [0] + [random.getrandbits(32) for _ in range(31)]   # values[i] goes into register i
    for i in range(1, 32):
        await write(dut, i, values[i])
    for i in range(1, 32):
        r1, r2 = await read(dut, i, 32 - i)     # rs1 and rs2 read different registers
        assert r1 == values[i], f"x{i}: got {r1:#x}, expected {values[i]:#x}"
        assert r2 == values[32 - i], f"x{32 - i}: got {r2:#x}, expected {values[32 - i]:#x}"

    # 3. Writing new value with we = 0; check nothing changed
    rand_addr = random.getrandbits(5)
    rand_data = random.getrandbits(32)
    await write(dut, rand_addr, rand_data, 0)  # we=0, addr=random, data=random
    r1, _ = await read(dut, rand_addr, 0)
    assert r1 == values[rand_addr], f"x{rand_addr}: got {r1:#x}, expected {values[rand_addr]:#x}"

    # 4. With we=1, writing to x0; check it still reads 0
    await write(dut, 0, random.getrandbits(32), 1)
    r1, _ = await read(dut, 0, 0)
    assert r1 == 0, f"x0: got {r1:#x}, expected 0"

    # 5. Overwrite: write x10 twice, check the second value stuck
    rand_data2 = random.getrandbits(32)
    await write(dut, 10, random.getrandbits(32))
    await write(dut, 10, rand_data2)
    r1, _ = await read(dut, 10, 0)
    assert r1 == rand_data2, f"x10: got {r1:#x}, expected {rand_data2:#x}"
    values[10] = rand_data2

    # 6. Set we/rd_addr/rd_data for x7 WITHOUT waiting for a clock edge,
    #    read x7 straight away (should still be the old value),
    #    then await FallingEdge(dut.clk) and read again (should be the new value)
    dut.we.value = 1
    dut.rd_addr.value = 7
    rand_data3 = random.getrandbits(32)
    dut.rd_data.value = rand_data3
    r1, _ = await read(dut, 7, 0)
    assert r1 == values[7], f"x7: got {r1:#x}, expected {values[7]:#x}"

    await FallingEdge(dut.clk)
    r1, _ = await read(dut, 7, 0)
    assert r1 == rand_data3, f"x7 after clock edge: got {r1:#x}, expected {rand_data3:#x}"
    dut.we.value = 0
    values[7] = rand_data3

def test_regfile():
    root = Path(__file__).resolve().parent.parent
    runner = get_runner("verilator")
    runner.build(
        sources=[root / "rtl" / "regfile.sv"],
        hdl_toplevel="regfile",
        build_dir=root / "sim_build",
        waves=True,
    )
    runner.test(hdl_toplevel="regfile", test_module="test_regfile", waves=True)