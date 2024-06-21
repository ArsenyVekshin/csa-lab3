class Memory:
    memory = None
    start_of_variables = None
    value = None

    def __init__(self, code, start_of_variables, buff_size):
        self.start_of_variables = start_of_variables
        self.memory = [0] * (len(code)+buff_size)
        self.value = 0
        for number, instruction in enumerate(code, 0):
            self.memory[number] = instruction

    def read(self, adr):
        self.value = self.memory[adr]

    def write(self, adr):
        self.memory[adr] = self.value

    def __repr__(self):
        out = ""
        for i in range(len(self.memory)):
            buff = ""
            if isinstance(self.memory[i], int): buff = str(self.memory[i])
            else: buff = self.memory[i].get_short_note()
            out += "{:4} : \t {}\n".format(i, buff)
        return out
