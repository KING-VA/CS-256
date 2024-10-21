"""
Dead Code Elimination for both local and global scope
"""
import json
import sys
import click
from basic_blocks import BasicBlock

def global_dead_code(fn):
    """Eliminate dead code from a global scope -- determine which instructions are used and remove the rest."""
    changed = True
    while changed:
        changed = False
        used = set()
        for instr in fn['instrs']:
            if 'args' in instr:
                for arg in instr['args']:
                    used.add(arg)
        for instr in fn['instrs']:
            if 'dest' in instr and instr['dest'] not in used:
                fn['instrs'].remove(instr)
                changed = True

def local_dead_code(func):
    """Eliminate dead code within a single block of instructions from a local scope -- catch reassignment."""
    blocks = BasicBlock.create_blocks_from_function(func['instrs'])
    for block in blocks:
        last_def = dict()
        for i, instr in enumerate(block.instructions):
            for arg in instr.get('args', []):
                last_def.pop(arg, None)
                
            if 'dest' in instr:
                dest = instr['dest']
                if dest in last_def:
                    block.pop(last_def[dest])
                last_def[dest] = i
    func['instrs'] = [inst for block in blocks for inst in block.instructions]

@click.command()
@click.option('--global', 'is_global', is_flag=True, default=False, help='Global Dead Code Elimination Flag')
def main(is_global):
    """ Main function for Dead Code Elimination -- parses input and calls dead_code_entry according to scope """
    prog = json.load(sys.stdin)
    if is_global:
        for fn in prog["functions"]:
            global_dead_code(fn)
    else:
        for fn in prog["functions"]:
            local_dead_code(fn)
    
    json.dump(prog, sys.stdout, indent=2)

if __name__ == "__main__":
    main()