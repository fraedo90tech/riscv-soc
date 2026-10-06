// A 4-bit adder: sum = a + b/
module adder (
	input logic [3:0] a,
	input logic [3:0] b,
	output logic [4:0] sum
);
	assign sum = a + b;
endmodule
