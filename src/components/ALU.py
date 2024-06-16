from enum import Enum


ALU_COMMANDS = [
    lambda x, y: 0,                         # CLA
    lambda x, y: -x,                        # NEG
    lambda x, y: x + 1,                     # INC
    lambda x, y: x - 1,                     # DEC
    lambda x, y: int(~bin(x), 2) - 1,       # NOT
    lambda x, y: int(bin(x) & bin(y), 2),   # AND
    lambda x, y: int(bin(x) | bin(y), 2),   # OR
    lambda x, y: x + y,                     # ADD
    lambda x, y: x - y,                     # SUB
    lambda x, y: x - y,                     # CMP
    lambda x, y: x * y,                     # MUL
    lambda x, y: x / y,                     # DIV
    lambda x, y: 1 if x == y else 0,        # BEQ
    lambda x, y: 1 if x > y else 0,         # BGT
    lambda x, y: 1 if x < y else 0          # BLT

]
MAX_NUMBER = 2**31 - 1
MIN_NUMBER = -(2**31)


class ALU:
    n_flag = None
    z_flag = None
    v_flag = None
    value = None
    first_value = None
    second_value = None

    def __init__(self):
        self.n_flag = 0
        self.z_flag = 0
        self.v_flag = 0
        self.value = 0
        self.first_value = 0
        self.second_value = 0

    def do_operation(self, command):
        if command is not None:
            alu = ALU_COMMANDS[command]
            result = alu(self.first_value, self.second_value)
            result = self.set_flags(result)
            self.value = result
        else:
            self.value = self.first_value

    def set_flags(self, result):
        self.n_flag = 0
        self.z_flag = 0
        self.v_flag = 0

        if result < 0:
            self.n_flag = 1

        if result == 0:
            self.z_flag = 1

        if result < MIN_NUMBER:
            result %= abs(MIN_NUMBER)
            self.v_flag = 1
        elif result > MAX_NUMBER:
            result %= MAX_NUMBER
            self.v_flag = 1

        return result
