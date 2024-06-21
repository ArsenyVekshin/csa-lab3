class StackOverflowError(Exception):
    def __init__(self, max_size):
        super().__init__(f"Error: stack is overflowed (max_size is {max_size})")

class Stack:
    stack = None
    max_size = None

    def __init__(self, max_size):
        self.stack = []
        self.max_size = max_size

    def push(self, arg):
        if len(self.stack) == self.max_size:
            raise StackOverflowError(self.max_size)
        if arg is not None:
            self.stack.append(arg)
    def pop(self):
        if len(self.stack) == 0:
            return None
        return self.stack.pop(-1)

    def __repr__(self):
        buff = ""
        for i in range(len(self.stack)-1, 0, -1):
            buff += str(self.stack[i]) + " "
        return buff
