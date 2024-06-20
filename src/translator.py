from __future__ import annotations

import json
import sys

from isa import Addressing, Instruction,  CodeEncoder, Opcode


# flake8: noqa: C901
def translate(text: str):
    code = []#: list[Instruction] = [Instruction(0, Opcode.NOP), Instruction(1, Opcode.NOP)]
    data: list[int] = []
    labels: dict[str, int] = {}
    prog_position: int = 0
    last_label: str = ""

    for line in text.splitlines():
        token = line.split(";", 1)[0].strip()
        if token == "":
            continue

        if token.endswith(":"):
            label = token.strip(":")
            assert label not in labels, "Redefinition of label: {}".format(label)
            labels[label] = prog_position
            last_label = label

        elif " " in token:
            sub_tokens = token.split(" ")
            assert len(sub_tokens) == 2, "Invalid instruction: {}".format(token)
            mnemonic, arg = sub_tokens
            if mnemonic == "WORD":
                code.append(Instruction(prog_position, Opcode.NOP, parse_number(arg)))
            else:
                opcode = Opcode(mnemonic)
                code.append(Instruction(prog_position, opcode, arg))
            prog_position += 1
        else:
            opcode = Opcode(token)
            code.append(Instruction(prog_position, opcode, addressing=Addressing.NONE.value))
            prog_position += 1
    return second_stage(code, labels)


# flake8: noqa: C901
def second_stage(code: list, labels: dict[str, int]):
    for instruction in code:
        if instruction.opcode is Opcode.NOP: continue
        if instruction.arg is not None:
            label = instruction.arg
            addressing = Addressing.DIRECT_ABS
            if label.startswith("["):
                if label.endswith("]"):
                    addressing = Addressing.DIRECT_SHIFT
                elif label.endswith("]+"):
                    addressing = Addressing.POST_INC
                elif label.endswith("]-"):
                    addressing = Addressing.POST_DEC
            elif label.startswith("#"):
                addressing = Addressing.LOAD
            label = label.strip("#[]+-")
            instruction.addressing = addressing.value
            try:
                instruction.arg = str(parse_number(label))
                continue
            except ValueError:
                pass
            assert label in labels, "Label not defined: {}".format(label)
            instruction.arg = str(labels[label])
    return code



def parse_number(label: str) -> int:
    if label.startswith("0x"):
        return int(label[2:], 16)
    return int(label)


def write_code(filename: str, code: list):
    with open(filename, "w", encoding="utf-8") as file:
        file.write(json.dumps(code, cls=CodeEncoder, indent=4))


def main(source: str, target: str):
    with open(source, encoding="utf-8") as f:
        source_text = f.read()

    code = translate(source_text)

    write_code(target, code)
    print("source LoC:", len(source.split("\n")), "code instr:", len(code))


if __name__ == "__main__":
    assert len(sys.argv) == 3, "Wrong arguments: translator.py <input_file> <target_file>"
    _, src, tar = sys.argv
    main(src, tar)
