import random
from pathlib import Path

import cocotb
from cocotb.triggers import Timer
from cocotb_tools.runner import get_runner

# Opcodes
OP, OP_IMM, LOAD, STORE = 0b0110011, 0b0010011, 0b0000011, 0b0100011
BRANCH, JAL, JALR = 0b1100011, 0b1101111, 0b1100111
LUI, AUIPC = 0b0110111, 0b0010111

# ALU operation codes (must match rtl/alu.sv)
ADD, SUB, AND, OR, XOR, SLL, SRL, SRA, SLT, SLTU = range(10)

# result_src values
R_ALU, R_MEM, R_PC4, R_IMM = 0, 1, 2, 3

# Every expected tuple is in this order:
# (reg_write, alu_src, alu_a_src, alu_op, mem_write, result_src, branch, jump)
KNOWN = [
    ("add x3, x1, x2",    0x002081B3, (1, 0, 0, ADD,  0, R_ALU, 0, 0)),
    ("sub x3, x1, x2",    0x402081B3, (1, 0, 0, SUB,  0, R_ALU, 0, 0)),
    ("sll x3, x1, x2",    0x002091B3, (1, 0, 0, SLL,  0, R_ALU, 0, 0)),
    ("slt x3, x1, x2",    0x0020A1B3, (1, 0, 0, SLT,  0, R_ALU, 0, 0)),
    ("sltu x3, x1, x2",   0x0020B1B3, (1, 0, 0, SLTU, 0, R_ALU, 0, 0)),
    ("xor x3, x1, x2",    0x0020C1B3, (1, 0, 0, XOR,  0, R_ALU, 0, 0)),
    ("srl x3, x1, x2",    0x0020D1B3, (1, 0, 0, SRL,  0, R_ALU, 0, 0)),
    ("sra x3, x1, x2",    0x4020D1B3, (1, 0, 0, SRA,  0, R_ALU, 0, 0)),
    ("or x3, x1, x2",     0x0020E1B3, (1, 0, 0, OR,   0, R_ALU, 0, 0)),
    ("and x3, x1, x2",    0x0020F1B3, (1, 0, 0, AND,  0, R_ALU, 0, 0)),
    ("addi x1, x0, 5",    0x00500093, (1, 1, 0, ADD,  0, R_ALU, 0, 0)),
    ("addi x1, x0, -1",   0xFFF00093, (1, 1, 0, ADD,  0, R_ALU, 0, 0)),  # bit 30 = 1, still ADD
    ("slli x1, x2, 3",    0x00311093, (1, 1, 0, SLL,  0, R_ALU, 0, 0)),
    ("srli x1, x2, 3",    0x00315093, (1, 1, 0, SRL,  0, R_ALU, 0, 0)),
    ("srai x1, x2, 3",    0x40315093, (1, 1, 0, SRA,  0, R_ALU, 0, 0)),
    ("andi x1, x2, 0xFF", 0x0FF17093, (1, 1, 0, AND,  0, R_ALU, 0, 0)),
    ("lw x5, 8(x1)",      0x0080A283, (1, 1, 0, ADD,  0, R_MEM, 0, 0)),
    ("sw x5, 8(x1)",      0x0050A423, (0, 1, 0, ADD,  1, R_ALU, 0, 0)),
    ("beq x1, x2, 16",    0x00208863, (0, 0, 0, SUB,  0, R_ALU, 1, 0)),
    ("bne x1, x2, -8",    0xFE209CE3, (0, 0, 0, SUB,  0, R_ALU, 1, 0)),
    ("blt x1, x2, 16",    0x0020C863, (0, 0, 0, SLT,  0, R_ALU, 1, 0)),
    ("bge x1, x2, 16",    0x0020D863, (0, 0, 0, SLT,  0, R_ALU, 1, 0)),
    ("bltu x1, x2, 16",   0x0020E863, (0, 0, 0, SLTU, 0, R_ALU, 1, 0)),
    ("bgeu x1, x2, 16",   0x0020F863, (0, 0, 0, SLTU, 0, R_ALU, 1, 0)),
    ("jal x1, 2048",      0x001000EF, (1, 0, 0, ADD,  0, R_PC4, 0, 1)),
    ("jalr x0, 0(x1)",    0x00008067, (1, 1, 0, ADD,  0, R_PC4, 0, 1)),
    ("lui x1, 0x12345",   0x123450B7, (1, 0, 0, ADD,  0, R_IMM, 0, 0)),
    ("auipc x1, 0x1",     0x00001097, (1, 1, 1, ADD,  0, R_ALU, 0, 0)),
    ("fence (unknown)",   0x0FF0000F, (0, 0, 0, ADD,  0, R_ALU, 0, 0)),  # does nothing
    ("ecall (unknown)",   0x00000073, (0, 0, 0, ADD,  0, R_ALU, 0, 0)),  # does nothing
]

# funct3 -> ALU operation, for OP and OP_IMM
FUNCT3_OP = {0: ADD, 1: SLL, 2: SLT, 3: SLTU, 4: XOR, 5: SRL, 6: OR, 7: AND}


def control_model(instr):
    opcode = instr & 0x7F
    funct3 = (instr >> 12) & 0x7
    bit30 = (instr >> 30) & 1

    alu_op = FUNCT3_OP[funct3]
    if funct3 == 0 and opcode == OP and bit30:
        alu_op = SUB
    if funct3 == 5 and bit30:
        alu_op = SRA

    if opcode == OP:
        return (1, 0, 0, alu_op, 0, R_ALU, 0, 0)
    if opcode == OP_IMM:
        return (1, 1, 0, alu_op, 0, R_ALU, 0, 0)
    if opcode == LOAD:
        return (1, 1, 0, ADD, 0, R_MEM, 0, 0)
    if opcode == STORE:
        return (0, 1, 0, ADD, 1, R_ALU, 0, 0)
    if opcode == BRANCH:
        # funct3 bits 2:1 pick the comparison: 00 = equal (SUB), 10 = SLT, 11 = SLTU
        branch_op = {0b10: SLT, 0b11: SLTU}.get(funct3 >> 1, SUB)
        return (0, 0, 0, branch_op, 0, R_ALU, 1, 0)
    if opcode == JAL:
        return (1, 0, 0, ADD, 0, R_PC4, 0, 1)
    if opcode == JALR:
        return (1, 1, 0, ADD, 0, R_PC4, 0, 1)
    if opcode == LUI:
        return (1, 0, 0, ADD, 0, R_IMM, 0, 0)
    if opcode == AUIPC:
        return (1, 1, 1, ADD, 0, R_ALU, 0, 0)
    return (0, 0, 0, ADD, 0, R_ALU, 0, 0)  # unknown opcode: do nothing


async def get_controls(dut, instr):
    dut.instr.value = instr
    await Timer(1, unit="ns")
    return (
        int(dut.reg_write.value),
        int(dut.alu_src.value),
        int(dut.alu_a_src.value),
        int(dut.alu_op.value),
        int(dut.mem_write.value),
        int(dut.result_src.value),
        int(dut.branch.value),
        int(dut.jump.value),
    )


@cocotb.test()
async def controlunit_works(dut):
    # 1. Real instructions with hand-checked answers
    for name, instr, expected in KNOWN:
        got = await get_controls(dut, instr)
        assert got == expected, f"{name} (0x{instr:08X}): expected {expected}, got {got}"

    # 2. Every possible opcode (all 128), with random other bits
    for opcode in range(128):
        for _ in range(50):
            instr = (random.getrandbits(25) << 7) | opcode
            got = await get_controls(dut, instr)
            expected = control_model(instr)
            assert got == expected, f"0x{instr:08X}: expected {expected}, got {got}"


def test_controlunit():
    root = Path(__file__).resolve().parent.parent
    runner = get_runner("verilator")
    runner.build(sources=[root / "rtl" / "controlunit.sv"], hdl_toplevel="controlunit",
                 build_dir=root / "sim_build", waves=True)
    runner.test(hdl_toplevel="controlunit", test_module="test_controlunit", waves=True)
