""" 
Forms basic blocks from a program or function.
"""
import json
import sys
from bril_constants import TERMINATING_INSTRUCTIONS
from typing_extensions import List, Any, Self, Generator

class BasicBlock(object):
    def __init__(self, instructions: List[Any] = []):
        self.instructions = instructions

        # Populated by the CGF
        self.pred = []
        self.succ = []

    def add_predecessor(self, block):
        if block not in self.pred:
            self.pred.append(block)

    def add_successor(self, block):
        if block not in self.succ:
            self.succ.append(block)

    def remove_predecessor(self, block):
        self.pred.remove(block)

    def remove_successor(self, block):
        self.succ.remove(block)

    def add_instruction(self, instr):
        self.instructions.append(instr)

    def has_instructions(self) -> bool:
        return len(self.instructions) > 0

    def __str__(self):
        return str(self.instructions)

    @staticmethod
    def create_blocks_from_function(instructions) -> List[Self]:
        ret_list = []
        for block in BasicBlock.blocks_generator(instructions):
            new_block = BasicBlock(block)
            if new_block.has_instructions():
                ret_list.append(new_block)
        return ret_list

    @staticmethod
    def blocks_generator(instructions) -> Generator[list]:
        cur_block = []
        for instr in instructions:
            if 'op' in instr:
                cur_block.append(instr)
                if instr['op'] in TERMINATING_INSTRUCTIONS:
                    yield cur_block
                    cur_block = []
            else:
                if cur_block:
                    yield cur_block
                cur_block = [instr]
        if cur_block:
            yield cur_block

def main():
    prog = json.load(sys.stdin)
    global_blocks = []
    for fn in prog["functions"]:
        program_blocks = BasicBlock.create_blocks_from_function(fn['instrs'])
        global_blocks.append(program_blocks)
        print("Global Block #" + str(len(global_blocks)))
        for block in program_blocks:
            print("Local Block #" + str(program_blocks.index(block)))
            print(block)

if __name__ == "__main__":
    main()