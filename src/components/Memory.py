class Memory:
    memory = None
    start_of_variables = None
    value = None

    def __init__(self, code, start_of_variables):
        self.start_of_variables = start_of_variables
        self.memory = [0] * len(code)
        self.value = 0
        for number, instraction in enumerate(code, 0):
            self.memory[number] = instraction

    def read(self, adr):
        self.value = self.memory[adr]

    def write(self, adr):
        self.memory[adr] = self.value

    def __repr__(self):
        buff = ""
        for i in range(len(self.memory)):
            buff += "{:4} : \t {}\n".format(i, self.memory[i])
        return buff