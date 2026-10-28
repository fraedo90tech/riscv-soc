import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge
from cocotb_tools.runner import get_runner

MASK = 0xFFFF_FFFF

# ---------- a tiny assembler: builds the 32-bit machine code for us ----------
def r_type(funct7, rs2, rs1, funct3, rd, opcode=0b0110011):
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode

def i_type(imm, rs1, funct3, rd, opcode=0b0010011):
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode

# R-type: rd = rs1 op rs2   (funct7 bit 30 picks sub / sra)
def add(rd, rs1, rs2):  return r_type(0b0000000, rs2, rs1, 0b000, rd)
def sub(rd, rs1, rs2):  return r_type(0b0100000, rs2, rs1, 0b000, rd)
def sll(rd, rs1, rs2):  return r_type(0b0000000, rs2, rs1, 0b001, rd)
def slt(rd, rs1, rs2):  return r_type(0b0000000, rs2, rs1, 0b010, rd)
def sltu(rd, rs1, rs2): return r_type(0b0000000, rs2, rs1, 0b011, rd)
def xor(rd, rs1, rs2):  return r_type(0b0000000, rs2, rs1, 0b100, rd)
def srl(rd, rs1, rs2):  return r_type(0b0000000, rs2, rs1, 0b101, rd)
def sra(rd, rs1, rs2):  return r_type(0b0100000, rs2, rs1, 0b101, rd)
def or_(rd, rs1, rs2):  return r_type(0b0000000, rs2, rs1, 0b110, rd)   # "or" is a Python word
def and_(rd, rs1, rs2): return r_type(0b0000000, rs2, rs1, 0b111, rd)   # so is "and"

# I-type: rd = rs1 op imm
def addi(rd, rs1, imm):  return i_type(imm, rs1, 0b000, rd)
def slti(rd, rs1, imm):  return i_type(imm, rs1, 0b010, rd)
def sltiu(rd, rs1, imm): return i_type(imm, rs1, 0b011, rd)
def xori(rd, rs1, imm):  return i_type(imm, rs1, 0b100, rd)
def ori(rd, rs1, imm):   return i_type(imm, rs1, 0b110, rd)
def andi(rd, rs1, imm):  return i_type(imm, rs1, 0b111, rd)

# Shifts by an immediate: the amount is imm[4:0]; srai also sets imm[10] (= instr bit 30)
def slli(rd, rs1, sh): return i_type(sh, rs1, 0b001, rd)
def srli(rd, rs1, sh): return i_type(sh, rs1, 0b101, rd)
def srai(rd, rs1, sh): return i_type(0x400 | sh, rs1, 0b101, rd)


# Loads (I-type, opcode LOAD): rd = mem[rs1 + imm]
def lb(rd, imm, rs1):  return i_type(imm, rs1, 0b000, rd, opcode=0b0000011)
def lh(rd, imm, rs1):  return i_type(imm, rs1, 0b001, rd, opcode=0b0000011)
def lw(rd, imm, rs1):  return i_type(imm, rs1, 0b010, rd, opcode=0b0000011)
def lbu(rd, imm, rs1): return i_type(imm, rs1, 0b100, rd, opcode=0b0000011)
def lhu(rd, imm, rs1): return i_type(imm, rs1, 0b101, rd, opcode=0b0000011)

# Stores (S-type): mem[rs1 + imm] = rs2. The imm is split: [11:5] in bits 31:25, [4:0] in bits 11:7
def s_type(imm, rs2, rs1, funct3, opcode=0b0100011):
    imm &= 0xFFF
    return ((imm >> 5) << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | ((imm & 0x1F) << 7) | opcode

def sb(rs2, imm, rs1): return s_type(imm, rs2, rs1, 0b000)
def sh(rs2, imm, rs1): return s_type(imm, rs2, rs1, 0b001)
def sw(rs2, imm, rs1): return s_type(imm, rs2, rs1, 0b010)


# Branches (B-type): if (rs1 ? rs2) PC += offset. The offset is shuffled like in immgen
def b_type(offset, rs2, rs1, funct3, opcode=0b1100011):
    o = offset & 0x1FFF
    return (((o >> 12) & 1) << 31) | (((o >> 5) & 0x3F) << 25) | (rs2 << 20) | (rs1 << 15) \
        | (funct3 << 12) | (((o >> 1) & 0xF) << 8) | (((o >> 11) & 1) << 7) | opcode

def beq(rs1, rs2, off):  return b_type(off, rs2, rs1, 0b000)
def bne(rs1, rs2, off):  return b_type(off, rs2, rs1, 0b001)
def blt(rs1, rs2, off):  return b_type(off, rs2, rs1, 0b100)
def bge(rs1, rs2, off):  return b_type(off, rs2, rs1, 0b101)
def bltu(rs1, rs2, off): return b_type(off, rs2, rs1, 0b110)
def bgeu(rs1, rs2, off): return b_type(off, rs2, rs1, 0b111)

# Jumps: rd = PC + 4 (the return address), then jump
def jal(rd, off):
    o = off & 0x1FFFFF
    return (((o >> 20) & 1) << 31) | (((o >> 1) & 0x3FF) << 21) | (((o >> 11) & 1) << 20) \
        | (((o >> 12) & 0xFF) << 12) | (rd << 7) | 0b1101111

def jalr(rd, imm, rs1): return i_type(imm, rs1, 0b000, rd, opcode=0b1100111)


HALT = beq(0, 0, 0)     # "branch to myself forever": the program's last line


def write_program(path, program):
    with open(path, "w") as f:
        for instr in program:
            f.write(f"{instr:08x}\n")


def reg(dut, n):
    """Peek inside the register file (x0 is always 0)."""
    return 0 if n == 0 else int(dut.u_regfile.regs[n].value)


async def run(dut, cycles):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst.value = 1
    await FallingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst.value = 0
    for _ in range(cycles):
        await FallingEdge(dut.clk)


ALU_AND_MEMORY = [
    # ---- group 1: add / addi ----
    addi(1, 0, 5),        # x1 = 5
    addi(2, 0, 10),       # x2 = 10
    add(3, 1, 2),         # x3 = 15
    addi(4, 3, -20),      # x4 = -5          (negative immediate)
    add(5, 4, 4),         # x5 = -10
    sub(6, 2, 1),         # x6 = 10 - 5 = 5
    addi(0, 0, 99),       # writing x0 must do nothing

    # ---- group 2: every other ALU op ----
    addi(7, 0, -1),       # x7  = 0xFFFFFFFF (all ones)
    sll(8, 2, 1),         # x8  = 10 << 5 = 320
    slt(9, 4, 1),         # x9  = (-5 < 5) signed           = 1
    sltu(10, 4, 1),       # x10 = (0xFFFFFFFB < 5) unsigned = 0
    xor(11, 2, 7),        # x11 = 10 ^ all-ones = ~10
    srl(12, 4, 1),        # x12 = 0xFFFFFFFB >> 5, zeros in  = 0x07FFFFFF
    sra(13, 4, 1),        # x13 = -5 >> 5, sign bit in       = -1
    or_(14, 1, 2),        # x14 = 0101 | 1010 = 15
    and_(15, 4, 2),       # x15 = ...1011 & 1010 = 10
    slti(16, 4, 0),       # x16 = (-5 < 0)                    = 1
    sltiu(17, 1, -1),     # x17 = (5 < 0xFFFFFFFF) unsigned   = 1
    xori(18, 1, -1),      # x18 = ~5                          (this is how "not" is done)
    ori(19, 1, 0x0F0),    # x19 = 0x05 | 0xF0 = 0xF5
    andi(20, 7, 0x7FF),   # x20 = all-ones & 0x7FF = 0x7FF
    slli(21, 1, 31),      # x21 = 5 << 31 = 0x80000000 (only the bottom 1 survives)
    srli(22, 21, 31),     # x22 = 0x80000000 >> 31, zeros in  = 1
    srai(23, 21, 31),     # x23 = 0x80000000 >> 31, sign in   = -1
    sub(24, 1, 2),        # x24 = 5 - 10 = -5

    # ---- group 3: loads and stores ----
    addi(25, 0, 0x100),   # x25 = 0x100, the base address
    addi(26, 0, -1234),   # x26 = -1234 = 0xFFFFFB2E
    sw(26, 0, 25),        # mem[0x100..0x103] = 2E FB FF FF  (little-endian)
    lw(27, 0, 25),        # x27 = 0xFFFFFB2E, the whole word back
    lb(28, 1, 25),        # x28 = byte at 0x101 = 0xFB, sign-extended   = 0xFFFFFFFB
    lbu(29, 1, 25),       # x29 = byte at 0x101 = 0xFB, zero-extended   = 0x000000FB
    lh(30, 2, 25),        # x30 = half at 0x102 = 0xFFFF, sign-extended = -1
    lhu(31, 0, 25),       # x31 = half at 0x100 = 0xFB2E, zero-extended
    sb(14, 3, 25),        # byte 0x103 = 15  -> word is now 0x0FFFFB2E
    sh(2, 0, 25),         # half 0x100 = 10  -> word is now 0x0FFF000A
    lw(26, 0, 25),        # x26 = 0x0FFF000A: only the bytes sb/sh touched changed
    HALT,
]

ALU_AND_MEMORY_EXPECTED = {
    0: 0, 1: 5, 2: 10, 3: 15, 4: -5, 5: -10, 6: 5,
    7: -1, 8: 320, 9: 1, 10: 0, 11: ~10, 12: 0x07FFFFFF, 13: -1, 14: 15, 15: 10,
    16: 1, 17: 1, 18: ~5, 19: 0xF5, 20: 0x7FF, 21: 0x80000000, 22: 1, 23: -1, 24: -5,
    25: 0x100, 26: 0x0FFF000A, 27: -1234, 28: -5, 29: 0xFB, 30: -1, 31: 0xFB2E,
}


# Each "check" sets a register to 7, then branches over an instruction that would set it to 1.
#   taken     -> the register stays 7
#   not taken -> the register becomes 1
BRANCHES = [
    # a loop: x1 = 5 + 4 + 3 + 2 + 1
    addi(1, 0, 0),        # 0x00  x1 = 0 (sum)
    addi(2, 0, 5),        # 0x04  x2 = 5 (counter)
    add(1, 1, 2),         # 0x08  loop: sum += counter
    addi(2, 2, -1),       # 0x0C  counter -= 1
    bne(2, 0, -8),        # 0x10  if counter != 0, back to 0x08
    # values to compare: -1 and 1. Signed, -1 is smaller; unsigned, -1 is 0xFFFFFFFF, the biggest
    addi(3, 0, -1),       # x3 = -1
    addi(4, 0, 1),        # x4 = 1
]
BRANCH_CHECKS = [         # (register, branch instruction, taken?)
    (10, beq(3, 3, 8),  True),     # -1 == -1
    (11, beq(3, 4, 8),  False),    # -1 == 1
    (12, bne(3, 4, 8),  True),
    (13, bne(3, 3, 8),  False),
    (14, blt(3, 4, 8),  True),     # -1 < 1 signed
    (15, blt(4, 3, 8),  False),
    (16, bge(4, 3, 8),  True),     # 1 >= -1 signed
    (17, bge(3, 4, 8),  False),
    (18, bltu(4, 3, 8), True),     # 1 < 0xFFFFFFFF unsigned
    (19, bltu(3, 4, 8), False),
    (20, bgeu(3, 4, 8), True),     # 0xFFFFFFFF >= 1 unsigned
    (21, bgeu(4, 3, 8), False),
    (22, bge(3, 3, 8),  True),     # equal counts as >=
]
for r, branch, _ in BRANCH_CHECKS:
    BRANCHES += [addi(r, 0, 7), branch, addi(r, 0, 1)]
BRANCHES += [HALT]

BRANCHES_EXPECTED = {1: 15, 2: 0}
BRANCHES_EXPECTED.update({r: 7 if taken else 1 for r, _, taken in BRANCH_CHECKS})


# A function call: "double x10" lives at 0x20, called with jal and returned from with jalr
JUMPS = [
    addi(10, 0, 7),       # 0x00  x10 = 7 (the function's argument)
    addi(12, 0, 7),       # 0x04  x12 = 7 (changes to 1 only if the skip below fails)
    jal(1, 0x20 - 0x08),  # 0x08  call the function: x1 = 0x0C, jump to 0x20
    addi(11, 10, 0),      # 0x0C  back here after the call: x11 = x10 = 14
    addi(6, 0, 0x28),     # 0x10  x6 = 0x28
    jalr(5, 1, 6),        # 0x14  jump to (0x28 + 1) with bit 0 cleared = 0x28; x5 = 0x18
    addi(12, 0, 1),       # 0x18  skipped
    HALT,                 # 0x1C  never reached
    add(10, 10, 10),      # 0x20  the function: x10 = x10 * 2
    jalr(0, 0, 1),        # 0x24  return: jump to x1, throw the return address away (rd = x0)
    HALT,                 # 0x28
]
JUMPS_EXPECTED = {10: 14, 11: 14, 1: 0x0C, 5: 0x18, 6: 0x28, 12: 7, 0: 0}


# name -> (program, expected registers)
PROGRAMS = {
    "alu_and_memory": (ALU_AND_MEMORY, ALU_AND_MEMORY_EXPECTED),
    "branches":       (BRANCHES, BRANCHES_EXPECTED),
    "jumps":          (JUMPS, JUMPS_EXPECTED),
}


@cocotb.test()
async def cpu_runs_program(dut):
    program, expected = PROGRAMS[os.environ["PROGRAM"]]
    await run(dut, 200)                   # plenty: every program ends in HALT
    for r, exp in expected.items():
        got = reg(dut, r)
        exp &= MASK                       # negative numbers -> 32-bit pattern
        assert got == exp, f"x{r}: got {got:#x}, expected {exp:#x}"


def test_cpu():
    root = Path(__file__).resolve().parent.parent
    build_dir = root / "sim_build"
    rtl = root / "rtl"
    runner = get_runner("verilator")
    runner.build(
        sources=[rtl / f for f in ["alu.sv", "regfile.sv", "pc.sv", "imem.sv", "dmem.sv",
                                   "immgen.sv", "controlunit.sv", "cpu.sv"]],
        hdl_toplevel="cpu",
        build_dir=build_dir,
        build_args=["--public-flat-rw"],
        waves=True,
    )
    for name, (program, _) in PROGRAMS.items():
        write_program(build_dir / "program.hex", program)
        runner.test(hdl_toplevel="cpu", test_module="test_cpu", test_dir=build_dir,
                    extra_env={"PROGRAM": name}, waves=True)
