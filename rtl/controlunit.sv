module controlunit(
    input logic [31:0] instr,
    output logic reg_write,
    output logic alu_src,
    output logic [3:0] alu_op,
    output logic mem_write,
    output logic [1:0]result_src, //00=ALU,01=MEM,10=PC+4,11=Uimm
    output logic branch,
    output logic jump,
    output logic alu_a_src
    );

logic [6:0] opcode;
logic [2:0] funct3;
logic [6:0] funct7;

assign opcode = instr[6:0];
assign funct3 = instr[14:12];
assign funct7 = instr[31:25];

localparam logic [6:0] OP = 7'b0110011;  // add, sub, and, or... (R)
localparam logic [6:0] OP_IMM = 7'b0010011;  // addi, andi... (I)
localparam logic [6:0] LOAD   = 7'b0000011;  // lw, lb...    (I)
localparam logic [6:0] JALR   = 7'b1100111;  // jalr         (I)
localparam logic [6:0] STORE  = 7'b0100011;  // sw, sb...    (S)
localparam logic [6:0] BRANCH = 7'b1100011;  // beq, bne, blt...  (B)
localparam logic [6:0] LUI    = 7'b0110111;  // (U)
localparam logic [6:0] AUIPC  = 7'b0010111;   // (U)
localparam logic [6:0] JAL    = 7'b1101111;   // (J)

localparam logic [3:0] ALU_ADD = 4'b0000, ALU_SUB = 4'b0001, ALU_AND = 4'b0010,
                       ALU_OR  = 4'b0011, ALU_XOR = 4'b0100, ALU_SLL = 4'b0101,
                       ALU_SRL = 4'b0110, ALU_SRA = 4'b0111, ALU_SLT = 4'b1000,
                       ALU_SLTU = 4'b1001;

logic [3:0] funct_op;

always_comb begin // Determine ALU operation based on funct3 and funct7
    case (funct3)
        3'b000: funct_op = (opcode == OP && funct7[5]) ? ALU_SUB : ALU_ADD;
        3'b001: funct_op = ALU_SLL;
        3'b010: funct_op = ALU_SLT;
        3'b011: funct_op = ALU_SLTU;
        3'b100: funct_op = ALU_XOR;
        3'b101: funct_op = funct7[5] ? ALU_SRA : ALU_SRL;
        3'b110: funct_op = ALU_OR;
        3'b111: funct_op = ALU_AND;
        default: funct_op = ALU_ADD;
    endcase
end
                       
always_comb begin // Default control signals for each instruction type
    // Default values
    reg_write = 1'b0;
    alu_src = 1'b0;
    alu_op = 4'b0000;
    mem_write = 1'b0;
    result_src = 2'b00;
    branch = 1'b0;
    jump = 1'b0;
    alu_a_src = 1'b0;

    case (opcode)
        OP: begin              // add x3, x1, x2: rd = rs1 op rs2
            reg_write  = 1'b1;
            alu_op     = funct_op;  // alu_src stays 0: second input is rs2
        end
        OP_IMM: begin          // addi x1, x0, 5: rd = rs1 op imm
            reg_write  = 1'b1;
            alu_src    = 1'b1;   // second input is the imm
            alu_op     = funct_op;
        end
        BRANCH: begin          // beq x1, x2, label
            branch     = 1'b1;   // no reg_write: branches don't touch rd
            case (funct3[2:1])
                2'b10: alu_op = ALU_SLT;
                2'b11: alu_op = ALU_SLTU;
                default: alu_op = ALU_SUB;
            endcase
        end
        JAL: begin             // jal x1, label: rd = PC+4, then jump
            reg_write  = 1'b1;
            jump       = 1'b1;
            result_src = 2'b10;  // write back PC+4
        end
        JALR: begin            // jalr x0, 0(x1): rd = PC+4, jump to rs1+imm
            reg_write  = 1'b1;
            jump       = 1'b1;
            alu_src    = 1'b1;   // ALU works out rs1 + imm = the target
            result_src = 2'b10;
        end
        LUI: begin             // lui x1, 0x12345: rd = imm
            reg_write  = 1'b1;
            result_src = 2'b11;  // write back the imm directly
        end
        AUIPC: begin           // auipc x1, 0x1: rd = PC + imm
            reg_write  = 1'b1;
            alu_a_src  = 1'b1;   // first input is PC
            alu_src    = 1'b1;   // second input is the imm
        end                      // result_src stays 00: the ALU result
        LOAD: begin
            reg_write  = 1'b1;
            alu_src    = 1'b1;
            result_src = 2'b01;
        end
        STORE: begin
            alu_src    = 1'b1;
            mem_write  = 1'b1;
        end
        default: ;
    endcase
end
endmodule
