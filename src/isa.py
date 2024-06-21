from __future__ import annotations

import json
from enum import Enum


class Opcode(str, Enum):
    # math with 1 argument
    CLA = "CLA"  # TOS * 0
    NEG = "NEG"  # TOS * (-1)
    INC = "INC"  # TOS + 1
    DEC = "DEC"  # TOS - 1

    # logic
    NOT = "NOT"
    AND = "AND"
    OR = "OR"

    # math with 2 arguments
    ADD = "ADD"  # TOS + X
    SUB = "SUB"  # TOS - X
    CMP = "CMP"  # TOS - X -> NZV
    MUL = "MUL"  # TOS * X
    DIV = "DIV"  # TOS / X
    SXTB = "SXTB"  # extend 8bit TOS

    # if (...) -> jmp to arg
    BEQ = "BEQ"  # TOS == X
    BGT = "BGT"  # TOS > X
    BLT = "BLT"  # TOS < X

    # mem
    LD = "LD"
    ST = "ST"

    # stack
    SWAP = "SWAP"
    DUP = "DUP"
    POP = "POP"

    # subprograms
    CALL = "CALL"
    JUMP = "JUMP"
    RET = "RET"

    # IO
    IN = "IN"  # send ready signal to device
    OUT = "OUT"  # check ready-status of device

    HLT = "HLT"
    NOP = "NOP"

    def __str__(self):
        return str(self.value)

    def index(self):
        return list(Opcode).index(self.value)


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

    def __repr__(self):
        return "{} : {} \n\t arg: {} \n\t addressing: {}\n".format(
            self.index,
            self.opcode,
            self.arg,
            self.addressing
        )

    def get_arg(self):
        return int(self.arg)

    def get_short_note(self):
        out = self.opcode
        if self.arg is not None:
            out += self.arg
        return out


class CodeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Instruction):
            return obj.__dict__
        return json.JSONEncoder.default(self, obj)
