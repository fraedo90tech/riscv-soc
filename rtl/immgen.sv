module immgen(
    input logic [31:0] instr,
    output logic [31:0] imm
);

localparam logic [6:0] OP_IMM = 7'b0010011;  // addi, andi... (I)
localparam logic [6:0] LOAD   = 7'b0000011;  // lw, lb...    (I)
localparam logic [6:0] JALR   = 7'b1100111;  // jalr         (I)
localparam logic [6:0] STORE  = 7'b0100011;  // sw, sb...    (S)
localparam logic [6:0] BRANCH = 7'b1100011;  // beq, bne, blt...  (B)
localparam logic [6:0] LUI    = 7'b0110111;  // (U)
localparam logic [6:0] AUIPC  = 7'b0010111;   // (U)
localparam logic [6:0] JAL    = 7'b1101111;   // (J)

always_comb begin
    case (instr[6:0])
        OP_IMM, LOAD, JALR: imm = {{20{instr[31]}}, instr[31:20]};  // I-type
        STORE:              imm = {{20{instr[31]}}, instr[31:25], instr[11:7]};  // S-type
        BRANCH:             imm = {{19{instr[31]}}, instr[31], instr[7], instr[30:25], instr[11:8], 1'b0};  // B-type
        LUI, AUIPC:         imm = {instr[31:12], 12'b0}; // U-type
        JAL:                imm = {{11{instr[31]}}, instr[31], instr[19:12], instr[20], instr[30:21], 1'b0}; // J-type
        default:            imm = 32'b0;
    endcase
end
endmodule
