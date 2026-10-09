module imem #(parameter int WORDS = 256)
(/* verilator lint_off UNUSEDSIGNAL */
    input logic [31:0] addr,
    output logic [31:0] instr);
        logic [31:0] mem [WORDS];
        initial begin
            $readmemh("program.hex", mem);
        end
        assign instr = mem[addr[9:2]];
endmodule
