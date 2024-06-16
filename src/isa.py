from __future__ import annotations

from enum import Enum

class Opcode(str, Enum):
    # math (x)
    CLA = "cla"     # TOS * 0
    NEG = "neg"     # TOS * (-1)
    INC = "inc"     # TOS + 1
    DEC = "dec"     # TOS - 1

    # logic
    NOT = "not"
    AND = "and"
    OR = "or"

    # math (x,y)
    ADD = "add"     # TOS + X
    SUB = "sub"     # TOS - X
    CMP = "cmp"     # TOS - X -> NZV
    MUL = "mul"     # TOS * X
    DIV = "div"     # TOS / X
    SXTB = "sxtb"   # extend 8bit TOS

    # if (...) -> jmp to arg
    BEQ = "beq"  # TOS == X
    BGT = "bgt"  # TOS > X
    BLT = "blt"  # TOS < X

    # mem
    LD = "ld"
    ST = "st"

    # stack
    SWAP = "swap"
    DUP = "dup"
    POP = "pop"

    # subprograms
    CALL = "call"
    JUMP = "jump"
    RET = "ret"

    # IO
    IN = "in"       # send ready signal to device
    OUT = "out"     # check ready-status of device

    def __str__(self):
        return str(self.value)

class Addressing(Enum):
    DIRECT_ABS = 0
    DIRECT_SHIFT = 1
    LOAD = 2
    POST_INC = 3
    POST_DEC = 4
    NONE = 5


class Instruction:
    def __init__(self, index: int, opcode: Opcode, arg: str | None = None, addressing: int = 0):
        self.index = index
        self.opcode = opcode
        self.arg = arg
        self.addressing = addressing
