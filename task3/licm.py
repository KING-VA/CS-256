import sys
import json
import copy
import click

from cfg import CFG
from ssa import SSA
from bril_constants import SPECIAL_OPERATIONS, TERMINATING_INSTRUCTIONS

import logging
logging.basicConfig(level=logging.DEBUG, filename='licm.log')
logger = logging.getLogger(__name__)

def variable_use_def_blocks(cfg) -> tuple[dict, dict]:
    """ Find the use and def blocks for each variable in the function """
    use_blocks = dict()
    def_blocks = dict()

    for block_name, block in cfg.items():
        for instr_idx, instr in enumerate(block.instructions):
            if 'args' in instr:
                for arg in instr['args']:
                    if arg not in use_blocks:
                        use_blocks[arg] = set()
                    use_blocks[arg].add((block_name, instr_idx))
            if 'dest' in instr:
                def_blocks[str(instr['dest'])] = (block_name, instr_idx)
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

def licm(function, debug=False) -> list:
    cfg_class = CFG.create_cfg_from_function(function['instrs'])
    if len(cfg_class.cfg) <= 1:
        return function['instrs']
    if debug:
        cfg_class.plot_cfg(CFG.DEFAULT_START_LABEL)
        cfg_class.plot_dominance_tree()
        logger.debug("CFG Backedges")
        logger.debug(cfg_class.back_edges)
        logger.debug("CFG Reducible")
        logger.debug(cfg_class.reducible)
        logger.debug("CFG Dominators")
        logger.debug(cfg_class.dominators)
        logger.debug("CFG Dominance Frontiers")
        logger.debug(cfg_class.dominance_frontiers)
        logger.debug("CFG Dominance Tree")
        logger.debug(cfg_class.dominance_tree)
        logger.debug("CFG Original")
        logger.debug(cfg_class.cfg)
    # SSA.cfg_to_ssa(cfg_class)
    if not cfg_class.reducible:
        return function['instrs']
    use_block, def_block = variable_use_def_blocks(cfg_class.cfg)
    cfg_copy = copy.deepcopy(cfg_class.cfg)
    if debug:
        logger.debug("Use Blocks")
        logger.debug(use_block)
        logger.debug("Def Blocks")
        logger.debug(def_block)
        logger.debug("CFG Copy") 
        logger.debug(cfg_copy)
        logger.debug("CFG Edges")
        logger.debug(cfg_class.edges)

    for backedge in cfg_class.back_edges:
        tail, header = backedge
        if not cfg_class.reachable(CFG.DEFAULT_START_LABEL, tail):
            if debug:
                logger.debug(f"Backedge {backedge} is not reachable from start label")
            continue
        preheader_blocks = set(
            [label for label, block in cfg_copy.items() if label in cfg_copy[header].pred]
        )
        loop_info = cfg_class.get_loop_information(backedge)
        for block_name in loop_info['nodes']:
            preheader_blocks.discard(block_name)
        if debug:
            logger.debug(f"Loop info for backedge {backedge}: {loop_info}")
            logger.debug(f"Preheader Blocks for header {header}: {preheader_blocks}")

        loop_invariant = set()
        while True:
            new_loop_invariant = copy.deepcopy(loop_invariant)
            for block_name in loop_info['nodes']:
                block = cfg_copy[block_name]
                for instr_idx, instr in enumerate(block.instructions):
                    if 'args' not in instr:
                        continue
                    if all(def_block[arg][0] not in loop_info['nodes'] for arg in instr['args'] if arg in def_block):
                        new_loop_invariant.add((block_name, instr_idx))
                    if all(def_block[arg] in new_loop_invariant for arg in instr['args'] if arg in def_block):
                        new_loop_invariant.add((block_name, instr_idx))
            if new_loop_invariant == loop_invariant:
                break
            loop_invariant = new_loop_invariant
        if debug:
            logger.debug(f"Loop Invariant Instructions: {loop_invariant}")
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
                if 'dest' not in instruction or instruction['dest'] == "":
                    i += 1
                    og_idx += 1
                    continue
                dest = instruction['dest']
                if dest not in use_block:
                    i += 1
                    og_idx += 1
                    continue
                if debug:
                    logger.debug(f"Checking instruction: {instr}")
                    logger.debug(f"Checking if {dest} is loop invariant")
                    for block_name_internal, instr_idx in use_block[dest]:
                        logger.debug(f"Block Name: {block_name_internal}, Instruction Index: {instr_idx}, Instruction: {cfg_copy[block_name_internal].instructions[instr_idx]}")
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
                    if len(preheader_block.instructions) <= 0 or not instruction_is_terminating(preheader_block.instructions[-1]):
                        preheader_block.instructions.append(instruction)
                    else:
                        preheader_block.instructions.insert(-1, instruction)
                popped_instruction = block.instructions.pop(i)
                og_idx += 1
                if debug:
                    logger.debug(f"Moved instruction {popped_instruction} from block {block_name} to preheader blocks {preheader_blocks}")
    if debug:
        logger.debug("CFG Pre SSA Conversion")
        logger.debug(cfg_copy)
    # SSA.ssa_to_cfg(cfg_copy)
    instruction_list = CFG.instructions_from_cfg(cfg_copy)
    if debug:
        logger.debug("CFG Post SSA Conversion")
        logger.debug(cfg_copy)
        logger.debug("Instruction List")
        logger.debug(instruction_list)
    return instruction_list

@click.command()
@click.option('--debug', 'is_debug', is_flag=True, default=False, help='Enable debugging')
def main(is_debug):
    # logging.basicConfig(filename='licm.log', level=logger.debug)
    logger.info("Starting LICM")
    prog = json.load(sys.stdin)
    for function in prog["functions"]:
        function["instrs"] = licm(function, debug=is_debug)
    logger.info("Finished LICM")
    json.dump(prog, sys.stdout, indent=2)

if __name__ == '__main__':
    main()