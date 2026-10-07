import random
from pathlib import Path

import cocotb
from cocotb.triggers import Timer
from cocotb_tools.runner import get_runner

MASK = 0xFFFF_FFFF          # keeps Python numbers to 32 bits


def to_signed(x):
    """Read a 32-bit pattern as a signed number."""
    return x - 2**32 if x & 0x8000_0000 else x


def alu_model(a, b, op):
    """ALU expected output."""
    sh = b & 0x1F                                   # shifts use bottom 5 bits
    if   op == 0: r = a + b                         # ADD
    elif op == 1: r = a - b                         # SUB
    elif op == 2: r = a & b                         # AND
    elif op == 3: r = a | b                         # OR
    elif op == 4: r = a ^ b                         # XOR
    elif op == 5: r = a << sh                       # SLL
    elif op == 6: r = a >> sh                       # SRL
    elif op == 7: r = to_signed(a) >> sh            # SRA
    elif op == 8: r = int(to_signed(a) < to_signed(b))  # SLT
    elif op == 9: r = int(a < b)                    # SLTU
    else:         r = 0                             # unused codes -> default
    return r & MASK


@cocotb.test()
async def alu_matches_model(dut):
    """Compare the ALU against alu_model for edge cases and random values."""
    edge = [0, 1, 2, 31, 32, 33, 0x7FFF_FFFF, 0x8000_0000, 0xFFFF_FFFF]
    pairs = [(a, b) for a in edge for b in edge]
    pairs += [(random.getrandbits(32), random.getrandbits(32)) for _ in range(200)]

    for a, b in pairs:
        for op in range(16):                        # 0-9 real ops, 10-15 hit default
            dut.a.value = a
            dut.b.value = b
            dut.alu_op.value = op
            await Timer(1, unit="ns")

            expected = alu_model(a, b, op)
            got = int(dut.result.value)
            assert got == expected, (
                f"op={op} a={a:#x} b={b:#x}: got {got:#x}, expected {expected:#x}"
            )
            assert int(dut.zero.value) == (expected == 0), f"zero wrong for op={op} a={a:#x} b={b:#x}"


def test_alu():
    root = Path(__file__).resolve().parent.parent
    runner = get_runner("verilator")
    runner.build(
        sources=[root / "rtl" / "alu.sv"],
        hdl_toplevel="alu",
        build_dir=root / "sim_build",
        waves=True,
    )
    runner.test(hdl_toplevel="alu", test_module="test_alu", waves=True)