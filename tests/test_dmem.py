import random
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, Timer, RisingEdge
from cocotb_tools.runner import get_runner

MASK = 0xFFFF_FFFF
LB, LH, LW, LBU, LHU = 0b000, 0b001, 0b010, 0b100, 0b101
SB, SH, SW = 0b000, 0b001, 0b010


# ---------- Python model: 1024 bytes, one per address ----------
def model_store(mem, addr, data, funct3):
    a = addr & 0x3FF                       # only bits 9:0 matter
    n = {SB: 1, SH: 2, SW: 4}[funct3]      # how many bytes
    for k in range(n):
        mem[a + k] = (data >> (8 * k)) & 0xFF   # lowest byte to lowest address


def model_load(mem, addr, funct3):
    a = addr & 0x3FF
    n = {LB: 1, LBU: 1, LH: 2, LHU: 2, LW: 4}[funct3]
    v = int.from_bytes(mem[a:a + n], "little")
    if funct3 in (LB, LH) and (v >> (8 * n - 1)) & 1:   # signed and top bit is 1
        v -= 1 << (8 * n)                               # make it negative
    return v & MASK


def aligned_addr(size):
    """Random address that's a multiple of size (1, 2 or 4)."""
    return random.randrange(0, 1024, size)


# ---------- helpers that drive the module ----------
async def store(dut, addr, data, funct3):
    dut.we.value = 1
    dut.addr.value = addr
    dut.wdata.value = data
    dut.funct3.value = funct3
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)     # the rising edge in between does the write
    dut.we.value = 0


async def load(dut, addr, funct3):
    dut.we.value = 0
    dut.addr.value = addr
    dut.funct3.value = funct3
    await Timer(1, unit="ns")      # reads are combinational, no clock needed
    return int(dut.rdata.value)

@cocotb.test()
async def dmem_works(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.we.value = 0
    await FallingEdge(dut.clk)
    mem = bytearray(1024)

    # 1. Fill every word with sw, then read each back with lw
    for i in range(256):
        data = random.getrandbits(32)
        await store(dut, i * 4, data, SW)
        model_store(mem, i * 4, data, SW)
    for i in range(256):
        got = await load(dut, i * 4, LW)
        exp = model_load(mem, i * 4, LW)
        assert got == exp, f"lw {i*4:#x}: got {got:#x}, expected {exp:#x}"

    # 2. Store a word, then read each byte with lb/lbu and each halfword with lh/lhu
    await store(dut, 0x08, 0xAABBCCDD, SW)
    model_store(mem, 0x08, 0xAABBCCDD, SW)
    for addr in range(0x08, 0x0C):
        got_lb = await load(dut, addr, LB)
        exp_lb = model_load(mem, addr, LB)
        assert got_lb == exp_lb, f"lb {addr:#x}: got {got_lb:#x}, expected {exp_lb:#x}"

        got_lbu = await load(dut, addr, LBU)
        exp_lbu = model_load(mem, addr, LBU)
        assert got_lbu == exp_lbu, f"lbu {addr:#x}: got {got_lbu:#x}, expected {exp_lbu:#x}"

    got_lh = await load(dut, 0x08, LH)
    exp_lh = model_load(mem, 0x08, LH)
    assert got_lh == exp_lh, f"lh 0x08: got {got_lh:#x}, expected {exp_lh:#x}"

    got_lh = await load(dut, 0x0A, LH)
    exp_lh = model_load(mem, 0x0A, LH)
    assert got_lh == exp_lh, f"lh 0x0A: got {got_lh:#x}, expected {exp_lh:#x}"

    got_lhu = await load(dut, 0x08, LHU)
    exp_lhu = model_load(mem, 0x08, LHU)
    assert got_lhu == exp_lhu, f"lhu 0x08: got {got_lhu:#x}, expected {exp_lhu:#x}"

    got_lhu = await load(dut, 0x0A, LHU)
    exp_lhu = model_load(mem, 0x0A, LHU)
    assert got_lhu == exp_lhu, f"lhu 0x0A: got {got_lhu:#x}, expected {exp_lhu:#x}"

    #3 Store a byte and check the word is updated corrctly
    await store(dut, 0x09, 0x123456EF, SB)
    model_store(mem, 0x09, 0x123456EF, SB)
    got_lw = await load(dut, 0x08, LW)
    exp_lw = model_load(mem, 0x08, LW)
    assert got_lw == exp_lw, f"lw 0x08: got {got_lw:#x}, expected {exp_lw:#x}"
    got_lbu = await load(dut, 0x09, LBU)
    assert got_lbu == 0xEF, f"lbu 0x09: got {got_lbu:#x}, expected 0xef"

    #4 50000 random operations.
    for i in range (50000):
        if random.random() < 0.5:
            f = random.choice([SB, SH, SW])
            addr = aligned_addr({SB:1, SH:2, SW:4}[f])
            data = random.getrandbits(32)
            await store(dut, addr, data, f)
            model_store(mem, addr, data, f)
        else:
            f = random.choice([LB, LH, LW, LBU, LHU])
            addr = aligned_addr({LB:1, LBU:1, LH:2, LHU:2, LW:4}[f])
            got = await load(dut, addr, f)
            exp = model_load(mem, addr, f)
            assert got == exp, f"load {addr:#x}: got {got:#x}, expected {exp:#x}"

    dut.we.value = 0
    dut.addr.value = 12
    dut.wdata.value = 0x12345678
    dut.funct3.value = SW
    await FallingEdge(dut.clk)
    result = await load(dut, 12, LW)
    assert result == model_load(mem, 12, LW), f"lw 12: got {result:#x}, expected {model_load(mem, 12, LW):#x}"


def test_dmem():
    root = Path(__file__).resolve().parent.parent
    runner = get_runner("verilator")
    runner.build(sources=[root / "rtl" / "dmem.sv"], hdl_toplevel="dmem",
                 build_dir=root / "sim_build", waves=True)
    runner.test(hdl_toplevel="dmem", test_module="test_dmem", waves=True)
