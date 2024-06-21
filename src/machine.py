import sys
import json
import logging

from components.ALU import ALU
from components.DataStack import Stack
from components.Memory import Memory
from components.Signals import TOSMux, ALUMux, DRSig, IPMux, ARMux
from isa import Opcode, Instruction, Addressing

STACK_SIZE = 64
SIZE_FOR_VARS = 150
INSTRUCTION_LIMIT = 100000

class WrongInstructionFormat(Exception):
    def __init__(self, instr, ip):
        super().__init__(f"Error: unable to parse instruction {instr} at ip = {ip} - wrong format")

class DataPath:
    def __init__(self, code, start_of_variables, input_tokens_size = SIZE_FOR_VARS):
        self.data_stack = Stack(STACK_SIZE)
        self.alu = ALU()
        self.memory = Memory(code, start_of_variables, input_tokens_size)
        self.ip = 1
        self.tos = 0
        self.ar = 0
        self.dr = 0
        self.br = 0

    def dataStack_push(self):
        self.data_stack.push(self.tos)

    def signal_latch_DR(self, signal=None):
        if signal is None: return
        match signal:
            case DRSig.READ:
                self.memory.read(self.ar)
                self.dr = self.memory.value
            case DRSig.WRITE:
                self.memory.value = self.dr
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
    def __init__(self, dataPath, inputBuffer, memAddr, output_file):
        self.iter = 0
        self.dataPath = dataPath
        self.inputBuffer = inputBuffer
        self.outputBuffer = []
        self.memAddr = memAddr
        self.output_file = output_file

    def __repr__(self):
        return "IN: {} OUT: {}".format(
            self.inputBuffer,
            self.outputBuffer
        )

    def get(self):
        assert self.iter < len(self.inputBuffer),(
            "Internal error: not enough symbols at buffer to read {} >= {}".format(self.iter, len(self.inputBuffer)))

        if type(self.inputBuffer[self.iter]) is not int:
            self.dataPath.memory.value = ord(self.inputBuffer[self.iter])
        else:
            self.dataPath.memory.value = self.inputBuffer[self.iter]
        self.dataPath.memory.write(self.memAddr)
        self.iter += 1

    def send(self):
        self.dataPath.memory.read(self.memAddr)
        self.outputBuffer.append(self.dataPath.memory.value)
        # print("OUT: ", self.outputBuffer)
    def finish(self):
        print(self.outputBuffer)
        file = open(self.output_file, "w+", encoding="utf-8")
        for s in self.outputBuffer:
            file.write(chr(s))
        file.close()

class ControlUnit:
    def __init__(self, dataPath: DataPath, ioController:IOController):
        self.dataPath = dataPath
        self.ioController = ioController
        self.return_stack = Stack(STACK_SIZE)
        self.cr = 0

    def __repr__(self):
        # buff = "IP: {:3} ".format(self.dataPath.ip)
        # buff += "CR"
        return "  IP: {:3} \tCR: {:4} \tAR: {:4} \tDR: {:4} \tBR: {:2} \tSTACK: {}".format(
            self.dataPath.ip,
            self.cr.getShortNote() if isinstance(self.cr, Instruction) else self.cr,
            self.dataPath.ar,
            self.dataPath.dr.getShortNote() if isinstance(self.dataPath.dr, Instruction) else self.dataPath.dr,
            self.dataPath.br,
            "[" + str(self.dataPath.tos) + " " + str(self.dataPath.data_stack) + "]",
        )


    def instructionFetch(self):
        self.dataPath.signal_latch_AR(ARMux.IP)
        self.dataPath.signal_latch_DR(DRSig.READ)
        self.cr = self.dataPath.dr

        if not isinstance(self.cr, Instruction):
            raise WrongInstructionFormat(self.cr, self.dataPath.ip)

        self.dataPath.signal_latch_ALU(ALUMux.IP)
        self.dataPath.alu_operation(Opcode.INC)
        self.dataPath.signal_latch_IP(IPMux.ALU)


    def addressFetch(self, cmd: Instruction):
        if cmd.addressing == Addressing.NONE.value: return

        if cmd.addressing == Addressing.DIRECT_ABS.value:
            # save current tos to DataStack
            self.dataPath.dataStack_push()
            self.dataPath.signal_latch_ALU(ALUMux.CR, cmd.getArg())
            self.dataPath.alu_operation(None)
            self.dataPath.signal_latch_DR(DRSig.NewValue)

            self.dataPath.signal_latch_TOS(TOSMux.DataStack)

        elif cmd.addressing == Addressing.LOAD.value:
            self.dataPath.signal_latch_ALU(ALUMux.CR, cmd.getArg())
            self.dataPath.alu_operation(None)
            self.dataPath.signal_latch_DR(DRSig.NewValue)
            return
        elif cmd.addressing == Addressing.DIRECT_SHIFT.value:
            # save current tos to DataStack
            self.dataPath.dataStack_push()

            # load current IP to DataStack
            self.dataPath.signal_latch_TOS(TOSMux.IP)
            self.dataPath.dataStack_push()

            # load shift value to TOS
            self.dataPath.signal_latch_TOS(TOSMux.CR, cmd.getArg())

            # we got targeted addr
            self.dataPath.alu_operation(Opcode.ADD)

        elif cmd.addressing in {Addressing.POST_INC.value, Addressing.POST_DEC.value}:
            # save current TOS to DataStack
            self.dataPath.dataStack_push()

            # read value from addr container
            self.dataPath.signal_latch_AR(ARMux.CR, cmd.getArg())
            self.dataPath.signal_latch_DR(DRSig.READ)
            self.dataPath.signal_latch_TOS(TOSMux.DR)

            # inc/dec addr container
            self.dataPath.signal_latch_ALU(ALUMux.TOS)
            if cmd.addressing == Addressing.POST_INC.value:
                self.dataPath.alu_operation(Opcode.INC)
            else:
                self.dataPath.alu_operation(Opcode.DEC)
            self.dataPath.signal_latch_DR(DRSig.NewValue)
            self.dataPath.signal_latch_DR(DRSig.WRITE)

            # read value from selected addr by container
            self.dataPath.signal_latch_ALU(ALUMux.TOS)
            self.dataPath.alu_operation(None)

            # return tos prev value
            self.dataPath.signal_latch_TOS(TOSMux.DataStack)
        self.operandFetch()


    def operandFetch(self):
        self.dataPath.signal_latch_AR(ARMux.ALU)
        self.dataPath.signal_latch_DR(DRSig.READ)

    def executionFetch(self, cmd: Instruction):

        # math \ logic \ if instructions
        if Opcode(cmd.opcode).index() <= Opcode.BLT.index():
            self.dataPath.signal_latch_ALU(ALUMux.TOS)
            self.dataPath.alu_operation(cmd.opcode)

            # extra actions for if
            if Opcode(cmd.opcode).index() >= Opcode.BEQ.index():
                if self.dataPath.alu.value == 1: # inc ip
                    self.dataPath.signal_latch_ALU(ALUMux.IP)
                    self.dataPath.alu_operation(Opcode.INC)
                    self.dataPath.signal_latch_IP(IPMux.ALU)
            else:
                self.dataPath.signal_latch_TOS(TOSMux.ALU)

        # LD
        elif cmd.opcode == Opcode.LD:
            self.dataPath.dataStack_push() # TOS -> stack
            self.dataPath.signal_latch_TOS(TOSMux.DR)

        # ST
        elif cmd.opcode == Opcode.ST:
            self.dataPath.signal_latch_ALU(ALUMux.TOS)
            self.dataPath.alu_operation(None)
            self.dataPath.signal_latch_DR(DRSig.NewValue)
            self.dataPath.signal_latch_DR(DRSig.WRITE)

        # JMP + CALL
        elif cmd.opcode in {Opcode.JUMP, Opcode.CALL}:
            if cmd.opcode is Opcode.CALL:
                self.return_stack.push(self.dataPath.ip)

            self.dataPath.signal_latch_IP(IPMux.ALU)

        # RET
        elif cmd.opcode == Opcode.RET:
            self.dataPath.signal_latch_IP(IPMux.ReturnStack, self.return_stack.pop())

        # SWAP
        elif cmd.opcode == Opcode.SWAP:
            self.dataPath.signal_latch_BR()
            self.dataPath.dataStack_push()
            self.dataPath.signal_latch_TOS(TOSMux.BR)

        # DUP
        elif cmd.opcode == Opcode.DUP:
            self.dataPath.dataStack_push()

        # POP
        elif cmd.opcode == Opcode.POP:
            self.dataPath.signal_latch_TOS(TOSMux.DataStack)

        # IN
        elif cmd.opcode == Opcode.IN:
            self.ioController.get()

        elif cmd.opcode == Opcode.OUT:
            self.ioController.send()

        elif cmd.opcode == Opcode.HLT:
            print("Got HLT cmd. Finishing execution...")
            self.ioController.finish()
            print(self.dataPath.memory)
            sys.exit(1)

    def execute(self):
        self.instructionFetch()
        cmd = self.cr
        self.addressFetch(cmd)
        self.executionFetch(cmd)


def simulation(code, input_tokens, limit, output_file):
    dataPath = DataPath(code, limit, input_tokens[0])
    ioController = IOController(dataPath, input_tokens, 0, output_file)
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

def main(code_file, input_file, output_file):
    with open(code_file, encoding="utf-8") as file:
        code = json.loads(file.read())
        machine_code = list(map(lambda d: Instruction(**d), code))

    # change NOP commands-signature to row data
    for i in range(len(machine_code)):
        if machine_code[i].opcode == Opcode.NOP.value:
            machine_code[i] = machine_code[i].arg

    input_text = []
    with open(input_file, encoding="utf-8") as file:
        input_text += list(file.readline())
    input_text = [len(input_text)-1] + input_text

    print(input_text)
    output, instr_counter, ticks = simulation(
        machine_code, input_text, INSTRUCTION_LIMIT, output_file
    )

    print("".join(output))


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    assert len(sys.argv) == 4, "Wrong arguments: machine.py <code_file> <input_file> <output_file>"
    _, code_file, input_file, output_file = sys.argv
    main(code_file, input_file, output_file)
