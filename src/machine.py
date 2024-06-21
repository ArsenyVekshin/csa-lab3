import json
import logging
import sys

from src.components.alu import ALU
from src.components.data_stack import Stack
from src.components.memory import Memory
from src.components.signals import ALUMux, ARMux, DRSig, IPMux, TOSMux
from src.isa import Addressing, Instruction, Opcode

INSTRUCTION_LIMIT = 100000
SIZE_FOR_VARS = 150
STACK_SIZE = 64

class WrongInstructionFormatError(Exception):
    def __init__(self, instr, ip):
        super().__init__(f"Error: unable to parse instruction {instr} at ip = {ip} - wrong format")


class DataPath:
    def __init__(self, code, start_of_variables, input_tokens_size=SIZE_FOR_VARS):
        self.data_stack = Stack(STACK_SIZE)
        self.alu = ALU()
        self.memory = Memory(code, start_of_variables, input_tokens_size)
        self.ip = 1
        self.tos = 0
        self.ar = 0
        self.dr = 0
        self.br = 0

    def data_stack_push(self):
        self.data_stack.push(self.tos)

    def signal_latch_dr(self, signal=None):
        if signal is None:
            return
        match signal:
            case DRSig.READ:
                self.memory.read(self.ar)
                self.dr = self.memory.value
            case DRSig.WRITE:
                self.memory.value = self.dr
                self.memory.write(self.ar)
            case DRSig.ALU:
                self.dr = self.alu.value

    def signal_latch_tos(self, signal=None, arg=None):
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

    def signal_latch_ip(self, signal=None, arg=None):
        match signal:
            case IPMux.ALU:
                self.ip = self.alu.value
            case IPMux.ReturnStack:
                self.ip = arg
                assert arg is not None, "Internal error: expected arg for RS -> IP"

    def signal_latch_ar(self, signal=None, arg=None):
        match signal:
            case ARMux.IP:
                self.ar = self.ip
            case ARMux.ALU:
                self.ar = self.alu.value
            case ARMux.CR:
                self.ar = arg
                assert arg is not None, "Internal error: expected arg for CR -> AR"

    def signal_latch_br(self, signal=None):
        self.br = self.data_stack.pop()

    def signal_latch_alu(self, signal=None, arg=None):
        match signal:
            case ALUMux.TOS:
                self.alu.first_value = self.tos
            case ALUMux.IP:
                self.alu.first_value = self.ip
            case ALUMux.CR:
                self.alu.first_value = arg
                assert arg is not None, "Internal error: expected arg for CR -> ALU"

    def alu_operation(self, command: Opcode = None):
        if command is not None:
            if Opcode.AND.index() <= Opcode(command).index() <= Opcode.BLT.index():
                self.alu.second_value = self.data_stack.pop()
        self.alu.do_operation(command)


class IOController:
    def __init__(self, data_path, input_buffer, mem_addr, output_file, output_mode):
        self.iter = 0
        self.data_path = data_path
        self.input_buffer = input_buffer
        self.outputBuffer = []
        self.memAddr = mem_addr
        self.output_file = output_file
        self.output_mode = output_mode

    def __repr__(self):
        return "IN: {} OUT: {}".format(
            self.input_buffer,
            self.outputBuffer
        )

    def get(self):
        assert self.iter < len(self.input_buffer), (
            "Internal error: not enough symbols at buffer to read {} >= {}".format(self.iter, len(self.input_buffer)))

        if not isinstance(self.input_buffer[self.iter], int):
            self.data_path.memory.value = ord(self.input_buffer[self.iter])
        else:
            self.data_path.memory.value = self.input_buffer[self.iter]
        self.data_path.memory.write(self.memAddr)
        self.iter += 1

    def send(self):
        self.data_path.memory.read(self.memAddr)
        self.outputBuffer.append(self.data_path.memory.value)

    def finish(self):
        file = open(self.output_file, "w+", encoding="utf-8")
        for s in self.outputBuffer:
            if self.output_mode == "text":
                file.write(chr(s))
            else:
                file.write(str(s))
                file.write(" ")
        file.close()


class ControlUnit:
    def __init__(self, data_path: DataPath, io_controller: IOController):
        self.data_path = data_path
        self.io_controller = io_controller
        self.return_stack = Stack(STACK_SIZE)
        self.cr = 0
        self._tick = 0

    def tick(self):
        self._tick += 1

    def __repr__(self):
        return "  TICK: {:4} \tIP: {:4} \tCR: {:4} \tAR: {:4} \tDR: {:4} \tBR: {:4} \tSTACK: {}".format(
            self._tick,
            self.data_path.ip,
            self.cr.get_short_note() if isinstance(self.cr, Instruction) else self.cr,
            self.data_path.ar,
            self.data_path.dr.get_short_note() if isinstance(self.data_path.dr, Instruction) else self.data_path.dr,
            self.data_path.br,
            "[" + str(self.data_path.tos) + " " + str(self.data_path.data_stack) + "]",
        )

    def instruction_fetch(self):
        self.data_path.signal_latch_ar(ARMux.IP)
        self.tick()
        self.data_path.signal_latch_dr(DRSig.READ)
        self.cr = self.data_path.dr
        self.tick()

        if not isinstance(self.cr, Instruction):
            raise WrongInstructionFormatError(self.cr, self.data_path.ip)

        self.data_path.signal_latch_alu(ALUMux.IP)
        self.tick()
        self.data_path.alu_operation(Opcode.INC)
        self.data_path.signal_latch_ip(IPMux.ALU)
        self.tick()

    def address_fetch(self, cmd: Instruction):
        if cmd.addressing == Addressing.NONE.value:
            return

        if cmd.addressing == Addressing.DIRECT_ABS.value:
            # save current tos to DataStack
            self.data_path.data_stack_push()
            self.tick()

            self.data_path.signal_latch_alu(ALUMux.CR, cmd.get_arg())
            self.data_path.alu_operation(None)
            self.data_path.signal_latch_dr(DRSig.ALU)
            self.tick()

            self.data_path.signal_latch_tos(TOSMux.DataStack)
            self.tick()

        elif cmd.addressing == Addressing.LOAD.value:
            self.data_path.signal_latch_alu(ALUMux.CR, cmd.get_arg())
            self.data_path.alu_operation(None)
            self.data_path.signal_latch_dr(DRSig.ALU)
            self.tick()
            return
        elif cmd.addressing == Addressing.DIRECT_SHIFT.value:
            # save current tos to DataStack
            self.data_path.data_stack_push()
            self.tick()

            # load current IP to DataStack
            self.data_path.signal_latch_tos(TOSMux.IP)
            self.tick()
            self.data_path.data_stack_push()
            self.tick()

            # load shift value to TOS
            self.data_path.signal_latch_tos(TOSMux.CR, cmd.get_arg())
            self.tick()

            # we got targeted addr
            self.data_path.alu_operation(Opcode.ADD)
            self.tick()

        elif cmd.addressing in {Addressing.POST_INC.value, Addressing.POST_DEC.value}:
            # save current TOS to DataStack
            self.data_path.data_stack_push()
            self.tick()

            # read value from addr container
            self.data_path.signal_latch_ar(ARMux.CR, cmd.get_arg())
            self.tick()
            self.data_path.signal_latch_dr(DRSig.READ)
            self.tick()
            self.data_path.signal_latch_tos(TOSMux.DR)
            self.tick()

            # inc/dec addr container
            self.data_path.signal_latch_alu(ALUMux.TOS)
            self.tick()
            if cmd.addressing == Addressing.POST_INC.value:
                self.data_path.alu_operation(Opcode.INC)
            else:
                self.data_path.alu_operation(Opcode.DEC)
            self.tick()
            self.data_path.signal_latch_dr(DRSig.ALU)
            self.tick()
            self.data_path.signal_latch_dr(DRSig.WRITE)
            self.tick()

            # read value from selected addr by container
            self.data_path.signal_latch_alu(ALUMux.TOS)
            self.data_path.alu_operation(None)
            # return tos prev value
            self.data_path.signal_latch_tos(TOSMux.DataStack)
            self.tick()
        self.operand_fetch()

    def operand_fetch(self):
        self.data_path.signal_latch_ar(ARMux.ALU)
        self.tick()
        self.data_path.signal_latch_dr(DRSig.READ)
        self.tick()

    def execution_fetch(self, cmd: Instruction):

        # math \ logic \ if instructions
        if Opcode(cmd.opcode).index() <= Opcode.BLT.index():
            self.data_path.signal_latch_alu(ALUMux.TOS)
            self.data_path.alu_operation(cmd.opcode)

            # extra actions for if
            if Opcode(cmd.opcode).index() >= Opcode.BEQ.index():
                if self.data_path.alu.value == 1:  # inc ip
                    self.tick()  # tick for read argument from stack
                    self.data_path.signal_latch_alu(ALUMux.IP)
                    self.data_path.alu_operation(Opcode.INC)
                    self.data_path.signal_latch_ip(IPMux.ALU)
            else:
                self.data_path.signal_latch_tos(TOSMux.ALU)
            self.tick()

        # LD
        elif cmd.opcode == Opcode.LD:
            self.data_path.data_stack_push()  # TOS -> stack
            self.tick()
            self.data_path.signal_latch_tos(TOSMux.DR)

        # ST
        elif cmd.opcode == Opcode.ST:
            self.data_path.signal_latch_alu(ALUMux.TOS)
            self.data_path.alu_operation(None)
            self.data_path.signal_latch_dr(DRSig.ALU)
            self.tick()
            self.data_path.signal_latch_dr(DRSig.WRITE)

        # JMP + CALL
        elif cmd.opcode in {Opcode.JUMP, Opcode.CALL}:
            if cmd.opcode is Opcode.CALL:
                self.return_stack.push(self.data_path.ip)
                self.tick()

            self.data_path.signal_latch_ip(IPMux.ALU)

        # RET
        elif cmd.opcode == Opcode.RET:
            self.data_path.signal_latch_ip(IPMux.ReturnStack, self.return_stack.pop())

        # SWAP
        elif cmd.opcode == Opcode.SWAP:
            self.data_path.signal_latch_br()
            self.tick()
            self.data_path.data_stack_push()
            self.tick()
            self.data_path.signal_latch_tos(TOSMux.BR)

        # DUP
        elif cmd.opcode == Opcode.DUP:
            self.data_path.data_stack_push()

        # POP
        elif cmd.opcode == Opcode.POP:
            self.data_path.signal_latch_tos(TOSMux.DataStack)

        # IN
        elif cmd.opcode == Opcode.IN:
            self.io_controller.get()

        elif cmd.opcode == Opcode.OUT:
            self.io_controller.send()

        elif cmd.opcode == Opcode.HLT:
            raise StopIteration
        self.tick()

    def execute(self):
        self.instruction_fetch()
        cmd = self.cr
        self.address_fetch(cmd)
        self.execution_fetch(cmd)


def simulation(code, input_tokens, limit, output_file, output_mode):
    data_path = DataPath(code, limit, input_tokens[0])
    io_controller = IOController(data_path, input_tokens, 0, output_file, output_mode)
    control_unit = ControlUnit(data_path, io_controller)
    instr_counter = 0

    logging.debug("%s", control_unit)
    try:
        while instr_counter < limit:
            control_unit.execute()
            instr_counter += 1
            logging.debug("%s", control_unit)
    except (StopIteration, EOFError):
        io_controller.finish()
        pass

    if instr_counter >= limit:
        logging.warning("Limit exceeded!")
    return instr_counter, control_unit._tick


def main(code_file, input_file, output_file, output_mode):
    with open(code_file, encoding="utf-8") as file:
        code = json.loads(file.read())
        machine_code = list(map(lambda d: Instruction(**d), code))

    # change NOP commands-signature to row data
    for i in range(len(machine_code)):
        if machine_code[i].opcode == Opcode.NOP.value:
            machine_code[i] = machine_code[i].arg

    input_text = []
    with open(input_file, encoding="utf-8") as file:
        buff = file.readline()
        if buff.startswith("["):
            input_text += eval(buff)
        else:
            input_text += list(buff)
    input_text = [len(input_text), *input_text]

    instr_counter, ticks = simulation(
        machine_code, input_text, INSTRUCTION_LIMIT, output_file, output_mode
    )
    print("instructions_executed: {} ticks: {}".format(instr_counter, ticks))


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    assert len(sys.argv) == 5, "Wrong arguments: machine.py <code_file> <input_file> <output_file> <output_mode>"
    _, code_file, input_file, output_file, output_mode = sys.argv
    main(code_file, input_file, output_file, output_mode)
