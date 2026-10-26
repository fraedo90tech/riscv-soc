import random
from pathlib import Path

import cocotb
from cocotb.triggers import Timer
from cocotb_tools.runner import get_runner

MASK = 0xFFFF_FFFF
OP_IMM, LOAD, JALR = 0b0010011, 0b0000011, 0b1100111
STORE, BRANCH = 0b0100011, 0b1100011
LUI, AUIPC, JAL = 0b0110111, 0b0010111, 0b1101111

# Real instructions with answers worked out like an assembler would
KNOWN = [
    ("addi x1,x0,5",   0x00500093, 0x00000005),
    ("addi x1,x0,-1",  0xFFF00093, 0xFFFFFFFF),
    ("sw x5,-4(x1)",   0xFE50AE23, 0xFFFFFFFC),
    ("beq x1,x2,-8",   0xFE208CE3, 0xFFFFFFF8),
    ("bne x1,x2,16",   0x00209863, 0x00000010),
    ("lui x1,0x12345", 0x123450B7, 0x12345000),
    ("jal x1,2048",    0x001000EF, 0x00000800),
    ("jal x0,-4",      0xFFDFF06F, 0xFFFFFFFC),
    ("add x3,x1,x2",   0x002081B3, 0x00000000),   # R-type: no immediate
]


def bits(x, hi, lo):
    """Python version of x[hi:lo]."""
    return (x >> lo) & ((1 << (hi - lo + 1)) - 1)

def sext(v, n):
    """Sign-extend an n-bit value to 32 bits."""
    if (v >> (n - 1)) & 1:
        v -= 1 << n
    return v & MASK


def imm_model(instr):
    op = instr & 0x7F
    if op in (OP_IMM, LOAD, JALR):                                   # I-type
        return sext(bits(instr, 31, 20), 12)
    if op == STORE:                                                  # S-type
        return sext((bits(instr, 31, 25) << 5) | bits(instr, 11, 7), 12)
    if op == BRANCH:                                                 # B-type
        return sext((bits(instr, 31, 31) << 12) | (bits(instr, 7, 7) << 11)
                    | (bits(instr, 30, 25) << 5) | (bits(instr, 11, 8) << 1), 13)
    if op in (LUI, AUIPC):                                           # U-type
        return bits(instr, 31, 12) << 12
    if op == JAL:                                                    # J-type
        return sext((bits(instr, 31, 31) << 20) | (bits(instr, 19, 12) << 12)
                    | (bits(instr, 20, 20) << 11) | (bits(instr, 30, 21) << 1), 21)
    return 0                                                         # R-type etc.


async def get_imm(dut, instr):
    dut.instr.value = instr
    await Timer(1, unit="ns")
    return int(dut.imm.value)


@cocotb.test()
async def immgen_works(dut):
    # 1. Real instructions with known answers
    for name, instr, expected in KNOWN:
        got = await get_imm(dut, instr)
        assert got == expected, f"{name}: got {got:#x}, expected {expected:#x}"

    # 2. 500 random instructions per opcode, checked against the model
    for op in (OP_IMM, LOAD, JALR, STORE, BRANCH, LUI, AUIPC, JAL):
        for _ in range(500):
            instr = (random.getrandbits(25) << 7) | op
            got = await get_imm(dut, instr)
            exp = imm_model(instr)
            assert got == exp, f"instr {instr:#010x}: got {got:#x}, expected {exp:#x}"


def test_immgen():
    root = Path(__file__).resolve().parent.parent
    runner = get_runner("verilator")
    runner.build(sources=[root / "rtl" / "immgen.sv"], hdl_toplevel="immgen",
                 build_dir=root / "sim_build", waves=True)
    runner.test(hdl_toplevel="immgen", test_module="test_immgen", waves=True)