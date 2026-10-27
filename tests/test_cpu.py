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

def add(rd, rs1, rs2):  return r_type(0b0000000, rs2, rs1, 0b000, rd)
def sub(rd, rs1, rs2):  return r_type(0b0100000, rs2, rs1, 0b000, rd)
def addi(rd, rs1, imm): return i_type(imm, rs1, 0b000, rd)


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


PROGRAM = [
    addi(1, 0, 5),      # x1 = 5
    addi(2, 0, 10),     # x2 = 10
    add(3, 1, 2),       # x3 = x1 + x2 = 15
    addi(4, 3, -20),    # x4 = 15 - 20 = -5
    add(5, 4, 4),       # x5 = -10
    sub(6, 2, 1),       # (sub isn't group 1, but OP already works)
    addi(0, 0, 99),     # writing x0 must do nothing
]
EXPECTED = {1: 5, 2: 10, 3: 15, 4: -5 & MASK, 5: -10 & MASK, 6: 5, 0: 0}


@cocotb.test()
async def cpu_add_addi(dut):
    await run(dut, len(PROGRAM))
    for r, exp in EXPECTED.items():
        got = reg(dut, r)
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
    write_program(build_dir / "program.hex", PROGRAM)
    runner.test(hdl_toplevel="cpu", test_module="test_cpu", test_dir=build_dir, waves=True)
