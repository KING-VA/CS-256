import sys
import json
import copy

from cfg import CFG
from ssa import SSA
from bril_constants import SPECIAL_OPERATIONS, TERMINATING_INSTRUCTIONS

def variable_use_def_blocks(cfg) -> tuple[dict, dict]:
    """ Find the use and def blocks for each variable in the function """
    use_blocks = dict()
    def_blocks = dict()

    for block_name, block in enumerate(cfg.items()):
        for instr_idx, instr in enumerate(block.instructions):
            if 'args' in instr:
                for arg in instr['args']:
                    use_blocks[arg].add((block_name, instr_idx))
            if 'dest' in instr:
                def_blocks[instr['dest']].add((block_name, instr_idx))
    return use_blocks, def_blocks

def instruction_can_error(instr) -> bool:
    if 'op' not in instr:
        return False
    if instr['op'] in ["free", "load", "store", "phi"] or (instr['op'] == "div" and instr['args'][1] == 0):
        return True
    return False

def instruction_is_terminating(instr) -> bool:
    if 'op' not in instr:
        return False
    if instr['op'] in TERMINATING_INSTRUCTIONS:
        return True
    return False

def licm(function) -> list:
    cfg_class = CFG(function)
    SSA.cfg_to_ssa(cfg_class)
    if not cfg_class.is_reducible():
        return function
    use_block, def_block = variable_use_def_blocks(cfg_class.cfg)
    cfg_copy = copy.deepcopy(cfg_class.cfg)

    for backedge in cfg_class.back_edges:
        tail, header = backedge
        if not cfg_class.reachable(CFG.DEFAULT_START_LABEL, tail):
            continue
        preheader_blocks = set(
            [label for label, block in cfg_copy.cfg.items() if header in block.pred]
        )
        loop_info = cfg_copy.get_loop_information(backedge)
        preheader_blocks -= loop_info['nodes']

        loop_invariant = set()
        while True:
            new_loop_invariant = copy.deepcopy(loop_invariant)
            for block_name in loop_info['nodes']:
                block = cfg_copy[block_name]
                for instr_idx, instr in enumerate(block.instructions):
                    if 'args' not in instr:
                        continue
                    if all(def_block[arg][0] not in loop_info['nodes'] for arg in instr['args']):
                        loop_invariant.add((block_name, instr_idx))
                    if all(def_block[arg] in new_loop_invariant for arg in instr['args']):
                        loop_invariant.add((block_name, instr_idx))
            if new_loop_invariant == loop_invariant:
                break
            loop_invariant = new_loop_invariant
        
        for block_name in loop_info['nodes']:
            block = cfg_copy[block_name]
            i = 0
            og_idx = 0
            while i < len(block.instructions):
                instruction = block.instructions[i]
                if (block_name, og_idx) not in loop_invariant:
                    i += 1
                    og_idx += 1
                    continue
                if 'dest' not in instruction:
                    i += 1
                    og_idx += 1
                    continue
                dest = instruction['dest']

                non_dominated_uses = [cfg_copy[block_name_internal].instructions[instr_idx] for block_name_internal, instr_idx in use_block[dest] if block_name not in cfg_class.dominators[block_name_internal]]

                if not (
                    len(non_dominated_uses) <= 0 or
                    all(
                        inst["op"] == "phi" and 
                        all(
                            label in loop_info['nodes']
                            for label in inst['labels']
                        )
                        for inst in non_dominated_uses
                    )
                ):
                    i += 1
                    og_idx += 1
                    continue
                if instruction["op"] in SPECIAL_OPERATIONS or instruction_can_error(instruction):
                    i += 1
                    og_idx += 1
                    continue
                for header_name in preheader_blocks:
                    preheader_block = cfg_copy[header_name]
                    if len(preheader_block) <= 0 or instruction_is_terminating(preheader_block.instructions[-1]):
                        preheader_block.instructions.append(instruction)
                    else:
                        preheader_block.instructions.insert(-1, instruction)
                block.instructions.pop(i)
                og_idx += 1
    return SSA.ssa_to_cfg(cfg_copy)

def main():
    prog = json.load(sys.stdin)
    for function in prog["functions"]:
        use_blocks, def_blocks = variable_use_def_blocks(function)
        print(json.dumps(use_blocks))
        print(json.dumps(def_blocks))
        print()

if __name__ == '__main__':
    main()