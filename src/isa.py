from __future__ import annotations

import json
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

    HLT = "hlt"

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

class MachineCode:
    def __init__(self, code: list[Instruction], data: list[int]):
        self.code: list[Instruction] = code
        self.data: list[int] = data


class CodeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Instruction):
            return obj.__dict__
        return json.JSONEncoder.default(self, obj)


class MachineCodeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, MachineCode):
            buf = []
            for code in obj.code:
                buf.append(code.__dict__)
            return {"code": buf, "data": obj.data}
        return json.JSONEncoder.default(self, obj)
