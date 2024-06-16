
from components.ALU import ALU
from components.DataStack import Stack
from components.Memory import Memory
from components.Signals import TOSMux, ALUMux, DRSig, IPMux, ARMux
from isa import Opcode, Instruction, Addressing



STACK_SIZE = 64
SIZE_FOR_VARS = 150
INSTRACTION_LIMIT = 100000


class DataPath:
    def __init__(self, code, input_token, start_of_variables):
        self.data_stack = Stack(STACK_SIZE)
        self.alu = ALU()
        self.memory = Memory(code, start_of_variables)
        self.ip = 1
        self.tos = None
        self.ar = None
        self.dr = None
        self.br = None
        self.input_buffer = input_token
        self.output_buffer = []

    def dataStack_push(self):
        self.data_stack.push(self.tos)

    def signal_latch_DR(self, signal=None):
        match signal:
            case DRSig.READ:
                self.memory.read(self.ar)
                self.dr = self.memory.value
            case DRSig.WRITE:
                self.memory.write(self.ar)
            case DRSig.NewValue:
                self.dr = self.alu.value

    def signal_latch_TOS(self, signal=None, arg = None):
        match signal:
            case TOSMux.BR:
                self.tos = self.br
            case TOSMux.DR:
                self.tos = self.dr
            case TOSMux.IP:
                self.tos = self.ip
            case TOSMux.ALU:
                self.tos = self.alu.value
            case TOSMux.DataStack:
                self.tos = self.data_stack.pop()
            case TOSMux.CR:
                self.tos = arg
                assert arg is not None, "Internal error: expected arg for CR -> TOS"

    def signal_latch_IP(self, signal=None, arg = None):
        match signal:
            case IPMux.ALU:
                self.ip = self.alu.value
            case IPMux.ReturnStack:
                self.ip = arg
                assert arg is not None, "Internal error: expected arg for RS -> IP"


    def signal_latch_AR(self, signal=None, arg = None):
        match signal:
            case ARMux.IP:
                self.ar = self.ip
            case ARMux.ALU:
                self.ar = self.alu.value
            case ARMux.CR:
                self.ar = arg
                assert arg is not None, "Internal error: expected arg for CR -> AR"

    def signal_latch_BR(self, signal=None):
        self.br = self.data_stack.pop()

    def signal_latch_ALU(self, signal=None, arg = None):
        match signal:
            case ALUMux.TOS:
                self.alu.first_value = self.tos
            case ALUMux.IP:
                self.alu.first_value = self.ip
            case ALUMux.CR:
                self.alu.first_value = arg
                assert arg is not None, "Internal error: expected arg for CR -> ALU"

    def alu_operation(self, command: Opcode):
        if Opcode.ADD <= command <= Opcode.DIV:
            self.alu.second_value = self.data_stack.pop()
        self.alu.do_operation(command)


class ControlUnit:
    def __init__(self, datapath):
        self.dataPath = datapath
        self.return_stack = Stack(STACK_SIZE)
        self.cr = None

    def instructionFetch(self):
        self.dataPath.signal_latch_AR(ARMux.IP)
        self.dataPath.signal_latch_DR(DRSig.READ)
        self.cr = self.dataPath.dr

        self.dataPath.signal_latch_ALU(ARMux.IP)
        self.dataPath.alu_operation(Opcode.INC)
        self.dataPath.signal_latch_IP(IPMux.ALU)


    def addressFetch(self, cmd: Instruction):
        if cmd.addressing is None: return

        if cmd.addressing is not Addressing.DIRECT_ABS:
            # save current tos to DataStack
            self.dataPath.dataStack_push()

            # load current IP to DataStack
            self.dataPath.signal_latch_TOS(TOSMux.IP)
            self.dataPath.dataStack_push()
            # load shift value to TOS
            self.dataPath.signal_latch_TOS(TOSMux.CR, cmd.arg)

            # we got targeted addr
            self.dataPath.alu_operation(Opcode.ADD)
            #self.dataPath.signal_latch_AR(ARMux.ALU)

            if cmd.addressing is not Addressing.DIRECT_SHIFT:
                self.dataPath.signal_latch_AR(ARMux.ALU)
                self.dataPath.signal_latch_DR(DRSig.READ)

                if cmd.addressing in {Addressing.POST_INC, Addressing.POST_DEC}:
                    self.dataPath.signal_latch_TOS(TOSMux.ALU)

                    self.dataPath.signal_latch_ALU(ALUMux.TOS)
                    if cmd.addressing is Addressing.POST_INC:
                        self.dataPath.alu_operation(Opcode.INC)
                    elif cmd.addressing is Addressing.POST_DEC:
                        self.dataPath.alu_operation(Opcode.DEC)

                    self.dataPath.signal_latch_DR(DRSig.NewValue)
                    self.dataPath.signal_latch_DR(DRSig.WRITE)

                    self.dataPath.signal_latch_ALU(ALUMux.TOS)
                    if cmd.addressing is Addressing.POST_INC:
                        self.dataPath.alu_operation(Opcode.DEC)
                    elif cmd.addressing is Addressing.POST_DEC:
                        self.dataPath.alu_operation(Opcode.INC)

            # return tos prev value
            self.dataPath.signal_latch_TOS(TOSMux.DataStack)


    def operandFetch(self):
        self.dataPath.signal_latch_AR(ARMux.ALU)
        self.dataPath.signal_latch_DR(DRSig.READ)

    def executionFetch(self, cmd: Instruction):

        # math \ logic \ if instructions
        if cmd.opcode <= Opcode.BLT:
            self.dataPath.signal_latch_ALU(ALUMux.TOS)
            self.dataPath.alu_operation(cmd)

            # extra actions for if
            if cmd.opcode >= Opcode.BEQ:
                if self.dataPath.alu.value == 1:
                    self.dataPath.signal_latch_IP(IPMux.ALU)
            else:
                self.dataPath.signal_latch_TOS(TOSMux.ALU)

        # LD
        if cmd.opcode is Opcode.LD:
            self.dataPath.dataStack_push() # TOS -> stack
            self.dataPath.signal_latch_TOS(TOSMux.DR)

        # ST
        if cmd.opcode is Opcode.ST:
            self.dataPath.signal_latch_ALU(ALUMux.TOS)
            self.dataPath.alu_operation(None)
            self.dataPath.signal_latch_DR(DRSig.NewValue)
            self.dataPath.signal_latch_DR(DRSig.WRITE)

        # JMP + CALL
        if cmd.opcode in {Opcode.JMP, Opcode.CALL}:
            if cmd.opcode is Opcode.CALL:
                self.return_stack.push(self.dataPath.ip)

            self.dataPath.signal_latch_IP(IPMux.ALU)

        # RET
        if cmd.opcode is Opcode.RET:
            self.dataPath.signal_latch_IP(IPMux.ReturnStack, self.return_stack.pop())

        # SWAP
        if cmd.opcode is Opcode.SWAP:
            self.dataPath.signal_latch_BR()
            self.dataPath.dataStack_push()
            self.dataPath.signal_latch_TOS(TOSMux.BR)

        # DUP
        if cmd.opcode is Opcode.DUP:
            self.dataPath.dataStack_push()

        # POP
        if cmd.opcode is Opcode.DUP:
            self.dataPath.signal_latch_TOS(TOSMux.DataStack)



