class Memory:
    memory = None
    start_of_variables = None
    value = None

    def __init__(self, code, start_of_variables):
        self.start_of_variables = start_of_variables
        self.memory = [0] * (len(code) + 1)
        self.value = 0
        self.memory[0] = start_of_variables
        for number, instraction in enumerate(code, 1):
            self.memory[number] = instraction

    def read(self, adr):
        self.value = self.memory[adr]

    def write(self, adr):
        self.memory[adr] = self.value
