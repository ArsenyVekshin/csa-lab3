import logging
import os
import re
import tempfile

import pytest

import src.translator as translator
import src.machine as machine

def replace_multiple_spaces_with_one(s):
    return re.sub(r"\s+", " ", s)

@pytest.mark.golden_test("golden/*.yml")
def test_bar(golden, caplog):
    caplog.set_level(logging.DEBUG)

    with tempfile.TemporaryDirectory() as tmpdir:
        source_file = os.path.join(tmpdir, "code.asm")
        target_file = os.path.join(tmpdir, "translator_output.txt")
        input_file = os.path.join(tmpdir, "input.txt")
        output_file = os.path.join(tmpdir, "output.txt")

        with open(input_file, "w", encoding="utf-8") as inp_file:
            inp_file.write(golden["in_stdin"])

        with open(source_file, "w", encoding="utf-8") as file:
            file.write(golden["in_source"])


        translator.main(source_file, target_file)
        print("=" * 5)
        print("target_file")
        #show target_file content
        with open(target_file, encoding="utf-8") as file:
            print(file.read())

        machine.main(target_file, input_file, output_file, golden["output_mode"])

        with open(target_file, encoding="utf-8") as file:
            human_readable = file.read()

        # assert human_readable.rstrip("\n") == golden.out["out_code_readable"].rstrip("\n")
        # open("file_log.txt", "w").write(caplog.text)
        # expected = replace_multiple_spaces_with_one(caplog.text.rstrip("\n").replace("\t","   "))
        # result = replace_multiple_spaces_with_one(golden.out["out_log"].rstrip("\n").replace("\t","    "))
        # assert expected == result