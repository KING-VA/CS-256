import copy
from cfg import CFG
import logging
from bril_constants import TERMINATING_INSTRUCTIONS
logging.basicConfig(level=logging.DEBUG, filename='licm.log')
logger = logging.getLogger(__name__)
class SSA(object):  
    @staticmethod
    def check_ssa(bril) -> bool:
        for func in bril['functions']:
            assigned = set()
            for instructions in func['instrs']:
                if 'dest' in instructions:
                    if instructions['dest'] in assigned:
                        return False
                    assigned.add(instructions['dest'])
        return True
    
    @staticmethod
    def ssa_to_cfg(cfg):
        for _, block in cfg.items():
            for instr in block.instructions:
                logger.debug(f"SSA Out Conversion Instruction: {instr}")
                if instr.get("op") == "phi":
                    dest = instr["dest"]
                    typ = instr["type"]

                    for i, label in enumerate(instr["labels"]):
                        var = instr["args"][i]
                        if var != 'undef':
                            copy_instr = {"op": "id", "type": typ, "args": [var], "dest": dest}
                            if cfg[label].instructions[-1]['op'] in TERMINATING_INSTRUCTIONS:
                                cfg[label].instructions.insert(-1, copy_instr)
                            else:
                                cfg[label].instructions.append(copy_instr)

            block.instructions = [
                instr for instr in copy.deepcopy(block.instructions) if instr.get("op") != "phi"
            ]

    @staticmethod
    def cfg_to_ssa(cfg: CFG):
        dominance_frontier = cfg.dominance_frontiers
        dominance_tree = cfg.dominance_tree
        defs, types, uses, input_variables = SSA.get_defs_uses_types_inputs(cfg)
        logger.debug(f"Defs: {defs}")
        logger.debug(f"Uses: {uses}")
        logger.debug(f"Types: {types}")
        logger.debug(f"Input Variables: {input_variables}")
        phi_blocks = SSA.find_phi_blocks(dominance_frontier, defs)
        logger.debug(f"Phi Blocks: {phi_blocks}")
        mapping_block_to_phi = SSA.rename_variables(cfg, phi_blocks, defs, dominance_tree, input_variables)
        logger.debug(f"Mapping Block to Phi: {mapping_block_to_phi}")
        SSA.insert_phi_nodes(cfg, mapping_block_to_phi, types)

    @staticmethod
    def get_defs_uses_types_inputs(cfg: CFG) -> tuple:
        defs = dict()
        types = dict()
        uses = dict()
        input_variables = dict()
        for label, block in cfg.cfg.items():
            for isntr_idx, instr in enumerate(block.instructions):
                if 'args' in instr:
                    for arg in instr['args']:
                        if arg not in uses:
                            uses[arg] = set()
                        uses[arg].add(label)
                        if arg not in input_variables:
                            input_variables[arg] = True
                if 'dest' in instr:
                    variable = instr['dest']
                    if variable not in defs:
                        defs[variable] = set()
                    defs[variable].add(label)
                    types[variable] = instr['type']
                    if variable not in input_variables:
                        input_variables[variable] = False
        return defs, types, uses, input_variables
    
    @staticmethod
    def find_phi_blocks(dominance_frontier: dict, defs: dict) -> dict:
        phi_blocks = {}
        for variable, def_blocks in defs.items():
            if len(def_blocks) <= 1:
                continue
            def_block_copy = copy.deepcopy(def_blocks)
            for label in def_block_copy:
                for block in dominance_frontier[label]:
                    if block not in phi_blocks:
                        phi_blocks[block] = set()
                    phi_blocks[block].add(variable)
                    defs[variable].add(block)
        return phi_blocks
    
    @staticmethod
    def rename_variables(cfg: CFG, phi_blocks: dict, defs: dict, dominance_tree: dict, input_variables) -> dict:      
        stack = {variable: [] for variable in defs.keys()}
        phi_node_info = {'dest': '', 'labels': [], 'args': []}
        mapping_block_to_phi = {block: {} for block in cfg.cfg.keys() if block in phi_blocks.keys()}

        for block_name_map in mapping_block_to_phi.keys():
            for variable in phi_blocks[block_name_map]:
                mapping_block_to_phi[block_name_map][variable] = copy.deepcopy(phi_node_info)

        def rename_helper(stack, block_name):
            block = cfg.cfg[block_name]
            saved_stack = copy.deepcopy(stack)
            if block_name in phi_blocks:
                for variables in phi_blocks[block_name]:
                    new_dest = f"{variables}.{len(stack[variables])}"
                    stack[variables].append(new_dest)
                    mapping_block_to_phi[block_name][variables]["dest"] = new_dest
            logger.debug(f"Variable Stack for block {block_name}: {stack}")
            for instruction in block.instructions:
                if 'args' in instruction:
                    instruction["args"] = [stack[arg][-1] if arg in stack and len(stack[arg]) else arg for arg in instruction["args"]]
                if 'dest' in instruction:
                    if instruction["dest"] in input_variables and input_variables[instruction["dest"]]:
                        continue
                    old_name = instruction["dest"]
                    new_dest = f"{old_name}.{len(stack[old_name])}"
                    instruction["dest"] = new_dest
                    stack[old_name].append(new_dest)
            for successor in cfg.cfg[block_name].succ:
                if successor in phi_blocks:
                    for variable in phi_blocks[successor]:
                        new_arg = stack[variable][-1] if block_name in defs[variable] else 'undef'
                        mapping_block_to_phi[successor][variable]["args"].append(new_arg)
                        mapping_block_to_phi[successor][variable]["labels"].append(block_name)
            
            for successor in dominance_tree[block_name].succ:
                rename_helper(stack, successor)

            stack.clear()
            stack.update(saved_stack)

        entry_block = list(cfg.cfg.keys())[0]
        rename_helper(stack, entry_block)
        return mapping_block_to_phi
    
    @staticmethod
    def insert_phi_nodes(cfg: CFG, mapping_block_to_phi: dict, types: dict):
        for block_name, phi_nodes in mapping_block_to_phi.items():
            for variable, phi_node in phi_nodes.items():
                phi_node = {
                    "op": "phi",
                    "dest": phi_node["dest"],
                    "type": types[variable],
                    "labels": phi_node["labels"],
                    "args": phi_node["args"]
                }
                cfg.cfg[block_name].instructions.insert(0, phi_node)