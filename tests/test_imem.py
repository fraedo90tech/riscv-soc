import random
from pathlib import Path

import cocotb
from cocotb.triggers import Timer
from cocotb_tools.runner import get_runner

@cocotb.test()
async def imem_works(dut):
    # Read back the same file the pytest function wrote
    with open("program.hex") as f:
        words = [int(line, 16) for line in f]

    # 1. Every slot returns its word
    for i in range(256):
        dut.addr.value = i * 4
        await Timer(1, unit="ns")
        got = int(dut.instr.value)
        assert got == words[i], f"slot {i} (addr {i*4:#x}): got {got:#x}, expected {words[i]:#x}"

    # 2. Generate 1000 random addresses and check that the returned instruction is correct
    for _ in range(1000):
        rand_addr = random.getrandbits(32) 
        dut.addr.value = rand_addr
        await Timer(1, unit="ns")
        got = int(dut.instr.value)
        assert got == words[(rand_addr >> 2) & 0xFF], f"addr {rand_addr:#x}: got {got:#x}, expected {words[(rand_addr >> 2) & 0xFF]:#x}"


def test_imem():
    root = Path(__file__).resolve().parent.parent
    build_dir = root / "sim_build"
    runner = get_runner("verilator")
    runner.build(
        sources=[root / "rtl" / "imem.sv"],
        hdl_toplevel="imem",
        build_dir=build_dir,
        waves=True,
    )

    # Fill all 256 slots with random 32-bit "instructions", one hex number per line
    words = [random.getrandbits(32) for _ in range(256)]
    with open(build_dir / "program.hex", "w") as f:
        for w in words:
            f.write(f"{w:08x}\n")

    runner.test(hdl_toplevel="imem", test_module="test_imem", test_dir=build_dir, waves=True)