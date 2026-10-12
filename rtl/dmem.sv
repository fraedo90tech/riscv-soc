module dmem #(parameter int WORDS = 256)
(/* verilator lint_off UNUSEDSIGNAL */
    input logic clk,
    input logic we,
    input logic [2:0] funct3,
    input logic [31:0] addr,
    input logic [31:0] wdata,
    output logic [31:0] rdata
);
        logic [31:0] mem [WORDS];
        logic [31:0] word;
        assign word = mem[addr[9:2]];
        logic [7:0] byte_val;
        logic [15:0] half_val;
        assign half_val = addr[1] ? word[31:16] : word[15:0]; //select the correct halfword based on addr[1]

        //Extract the correct byte from the word based on the address offset (addr[1:0]).
        always_comb begin
            case (addr[1:0])
                2'b00: byte_val = word[7:0]; // 1st Byte
                2'b01: byte_val = word[15:8]; // 2nd Byte
                2'b10: byte_val = word[23:16]; // 3rd Byte
                2'b11: byte_val = word[31:24]; // 4th Byte
            endcase
        end
        
        //The funct3 signal determines the size of the read (byte, halfword, or word) and whether to sign-extend or zero-extend the result.
        always_comb begin
            case (funct3[2:0])
                3'b000: rdata = {{24{byte_val[7]}}, byte_val[7:0]}; // LB
                3'b001: rdata = {{16{half_val[15]}}, half_val[15:0]}; // LH
                3'b010: rdata = word; // LW
                3'b100: rdata = {24'b0, byte_val[7:0]}; // LBU
                3'b101: rdata = {16'b0, half_val[15:0]}; // LHU
                default: rdata = word; // default to LW for other funct3 values
            endcase
        end

        //Write to memory on the rising edge of the clock if we is high. The funct3 signal determines the size of the write (byte, halfword, or word).
        always_ff @(posedge clk) begin
            if (we) begin
                case (funct3)
                    3'b000: case (addr[1:0])
                                2'b00: mem[addr[9:2]][7:0] <= wdata[7:0]; // SB
                                2'b01: mem[addr[9:2]][15:8] <= wdata[7:0]; // SB
                                2'b10: mem[addr[9:2]][23:16] <= wdata[7:0]; // SB
                                2'b11: mem[addr[9:2]][31:24] <= wdata[7:0]; // SB
                            endcase
                    3'b001: case (addr[1])
                                1'b0: mem[addr[9:2]][15:0] <= wdata[15:0]; // SH
                                1'b1: mem[addr[9:2]][31:16] <= wdata[15:0]; // SH
                            endcase
                    3'b010: mem[addr[9:2]] <= wdata; // SW
                    default: ; // Do nothing for other funct3 values
                endcase
            end
        end
endmodule
