import sys
import json
import logging

from components.ALU import ALU
from components.DataStack import Stack
from components.Memory import Memory
from components.Signals import TOSMux, ALUMux, DRSig, IPMux, ARMux
from isa import Opcode, Instruction, Addressing, MachineCode

STACK_SIZE = 64
SIZE_FOR_VARS = 150
INSTRUCTION_LIMIT = 100000

class WrongInstructionFormat(Exception):
    def __init__(self, instr, ip):
        super().__init__(f"Error: unable to parse instruction {instr} at ip = {ip} - wrong format")

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
        if signal is None: return
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

    def alu_operation(self, command: Opcode = None):
        if command is not None and Opcode.ADD <= command <= Opcode.DIV:
            self.alu.second_value = self.data_stack.pop()
        self.alu.do_operation(command)


class IOController:
    def __init__(self, dataPath, inputBuffer, memAddr):
        self.iter = 0
        self.dataPath = dataPath
        self.inputBuffer = inputBuffer
        self.outputBuffer = []
        self.memAddr = memAddr

    def __repr__(self):
        return "IN: {} OUT: {}".format(
            self.inputBuffer,
            self.outputBuffer
        )

    def get(self):
        assert self.iter >= len(self.inputBuffer), "Internal error: not enough symbols at buffer to read"
        self.dataPath.memory.value = self.inputBuffer[self.iter]
        self.dataPath.memory.write(self.memAddr)
        self.iter += 1

    def send(self):
        self.dataPath.memory.read(self.memAddr)
        self.outputBuffer.append(self.dataPath.memory.value)


class ControlUnit:
    def __init__(self, dataPath: DataPath, ioController:IOController):
        self.dataPath = dataPath
        self.ioController = ioController
        self.return_stack = Stack(STACK_SIZE)
        self.cr = None

    def __repr__(self):
        return "IP: {:3} CR: {:3} AR: {:3} DR: {:3} BR: {:3} \n\tSTACK: {} RETURN_STACK: {} \n\tMEMORY: {}".format(
            self.dataPath.ip,
            self.cr,
            self.dataPath.ar,
            self.dataPath.dr,
            self.dataPath.br,
            [self.dataPath.tos] + self.dataPath.data_stack.stack,
            self.return_stack.stack,
            self.dataPath.memory
        )

    def instructionFetch(self):
        self.dataPath.signal_latch_AR(ARMux.IP)
        self.dataPath.signal_latch_DR(DRSig.READ)
        self.cr = self.dataPath.dr

        if not isinstance(self.cr, Instruction):
            raise WrongInstructionFormat(self.cr, self.dataPath.ip)

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
            self.dataPath.alu_operation(cmd.opcode)

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

        # IN
        if cmd.opcode is Opcode.IN:
            self.ioController.get()

        if cmd.opcode is Opcode.OUT:
            self.ioController.send()

        if cmd.opcode is Opcode.HLT:
            print("Got HLT cmd. Finishing execution...")
            sys.exit(1)

    def execute(self):
        self.instructionFetch()
        cmd = self.cr
        self.addressFetch(cmd)
        self.executionFetch(cmd)


def simulation(code, input_tokens, data_memory, data_memory_size, limit):
    dataPath = DataPath(data_memory, data_memory_size, input_tokens)
    ioController = IOController(dataPath, input_tokens, 0)
    controlUnit = ControlUnit(dataPath, ioController)
    instr_counter = 0

    logging.debug("%s", controlUnit)
    try:
        while instr_counter < limit:
            controlUnit.execute()
            instr_counter += 1
            logging.debug("%s", controlUnit)
    except (StopIteration, EOFError):
        pass

    if instr_counter >= limit:
        logging.warning("Limit exceeded!")
    logging.info("output_buffer: %s", repr("".join(controlUnit.ioController.outputBuffer)))
    return "".join(dataPath.output_buffer), instr_counter, dataPath.ip

def main(code_file, input_file):
    with open(code_file, encoding="utf-8") as file:
        code = json.loads(file.read())
        print(code['data'])
        machine_code = MachineCode(list(map(lambda d: Instruction(**d), code["code"])), code["data"])
    with open(input_file, encoding="utf-8") as file:
        input_text = sorted(json.loads(file.read()), reverse=True)

    output, instr_counter, ticks = simulation(
        machine_code.code, input_text, machine_code.data, SIZE_FOR_VARS, INSTRUCTION_LIMIT
    )

    print("".join(output))


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    assert len(sys.argv) == 3, "Wrong arguments: machine.py <code_file> <input_file>"
    _, code_file, input_file = sys.argv
    main(code_file, input_file)
