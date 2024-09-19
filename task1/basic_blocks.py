""" 
Forms basic blocks from a program or function.
"""
import json
import sys
from bril_constants import FORKING_INSTRUCTIONS

def create_blocks(instructions):
    blocks = []
    # Use the block generator to create blocks list
    for block in blocks_generator(instructions):
        blocks.append(block)
    return blocks

def blocks_generator(instructions):
    cur_block = []
    for instr in instructions:
        if 'op' in instr:
            cur_block.append(instr)
            if instr['op'] in FORKING_INSTRUCTIONS:
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
        program_blocks = list(create_blocks(fn["instrs"]))
        global_blocks.append(program_blocks)
        print("Global Block #" + str(len(global_blocks)))
        for block in program_blocks:
            print("Local Block #" + str(program_blocks.index(block)))
            print(block)

if __name__ == "__main__":
    main()