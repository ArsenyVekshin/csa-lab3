from enum import Enum

class TOSMux(Enum):
    BR = 0
    DR = 1
    IP = 2
    ALU = 3
    DataStack = 4

class ALUMux(Enum):
    TOS = 0
    IP = 1
    CR = 2


class IPMux(Enum):
    ALU = 0
    ReturnStack = 1

class ARMux(Enum):
    ALU = 0
    CR = 1
    IP = 2



class DRSig(Enum):
    READ = 0
    WRITE = 1
    NewValue = 2


