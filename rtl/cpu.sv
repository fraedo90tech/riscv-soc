module cpu(
    input logic clk,
    input rst
);

logic [31:0] pc_cur;
logic [31:0] pc_next;
logic [31:0] instr;
logic [31:0] imm;
logic [31:0] rs1_data;
logic [31:0] rs2_data;
logic [31:0] alu_a;
logic [31:0] alu_b;
logic [31:0] alu_result;
logic alu_zero;
logic [31:0] mem_rdata;
logic [31:0] result;
logic [31:0] pc_plus4;

//branch wires
logic [31:0] pc_target;
logic cond;
logic taken;

//control unit outputs
logic reg_write;
logic alu_src;
logic [3:0] alu_op;
logic mem_write;
logic [1:0]result_src; //00=ALU,01=MEM,10=PC+4,11=Uimm
logic branch;
logic jump;
logic alu_a_src;

pc u_pc(
    .clk(clk), 
    .rst(rst), 
    .pc_next(pc_next),
    .pc_out(pc_cur)
    );

imem u_imem(
    .addr(pc_cur), 
    .instr(instr)
    );

controlunit u_controlunit(
    .instr(instr), 
    .reg_write(reg_write),
    .alu_src(alu_src),
    .alu_op(alu_op),
    .mem_write(mem_write),
    .result_src(result_src),
    .branch(branch),
    .jump(jump),
    .alu_a_src(alu_a_src)
    );

immgen u_immgen (
    .imm(imm),
    .instr(instr)
);

regfile u_regfile (
    .clk(clk), 
    .we(reg_write),
    .rs1_addr(instr[19:15]), 
    .rs2_addr(instr[24:20]), 
    .rd_addr(instr[11:7]),
    .rd_data(result),
    .rs1_data(rs1_data), 
    .rs2_data(rs2_data)
);

alu u_alu(
    .a(alu_a), 
    .b(alu_b), 
    .alu_op(alu_op), 
    .result(alu_result), 
    .zero(alu_zero)
);

dmem u_dmem(
    .clk(clk),
    .we(mem_write),
    .funct3(instr[14:12]),
    .addr(alu_result),
    .rdata(mem_rdata),
    .wdata(rs2_data)
);

//branch logic
assign cond = instr[14] ? !alu_zero : alu_zero;
assign taken = branch && (cond ^ instr[12]);
assign pc_target = pc_cur +imm;

assign alu_a = alu_a_src ? pc_cur : rs1_data;
assign pc_plus4  = pc_cur + 32'd4;              // next instruction
assign alu_b   = alu_src ? imm : rs2_data;    // addi uses imm, add uses rs2

always_comb begin
    if (instr [6:0] == 7'b1100111)
        pc_next = {alu_result[31:1], 1'b0};
    else if (instr [6:0] == 7'b1101111 || taken)
        pc_next = pc_target;
    else
        pc_next = pc_plus4;
end

always_comb begin
    case (result_src)
    2'b00: result = alu_result;
    2'b01: result = mem_rdata;
    2'b10: result = pc_plus4;
    2'b11: result = imm;
    endcase
end

endmodule
