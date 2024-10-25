import copy
from cfg import CFG

class SSA_OLD(object):  
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
                if instr.get("op") == "phi":
                    dest = instr["dest"]
                    typ = instr["type"]

                    for i, label in enumerate(instr["labels"]):
                        var = instr["args"][i]
                        if var != 'undef':
                            if var == dest:
                                continue
                            else:
                                copy_instr = {"op": "id", "type": typ, "args": [var], "dest": dest}
                                cfg[label].instructions.insert(-1, copy_instr)

            block.instructions = [
                instr for instr in copy.deepcopy(block.instructions) if instr.get("op") != "phi"
            ]

    @staticmethod
    def cfg_to_ssa(cfg: CFG):
        dominance_frontier = cfg.dominance_frontiers
        dominance_tree = cfg.dominance_tree
        defs, types = SSA.get_defs_and_types(cfg)
        phi_blocks = SSA.find_phi_blocks(dominance_frontier, defs)
        mapping_block_to_phi = SSA.rename_variables(cfg, phi_blocks, defs, dominance_tree)
        SSA.insert_phi_nodes(cfg, mapping_block_to_phi, types)

    @staticmethod
    def get_defs_and_types(cfg: CFG) -> tuple:
        defs = dict()
        types = dict()
        for label, block in cfg.cfg.items():
            for instr in block.instructions:
                if 'dest' in instr:
                    variable = instr['dest']
                    if variable not in defs:
                        defs[variable] = set()
                    defs[variable].add(label)
                    types[variable] = instr['type']
        return defs, types
    
    @staticmethod
    def find_phi_blocks(dominance_frontier: dict, defs: dict) -> dict:
        phi_blocks = {}
        for variable, def_blocks in defs.items():
            def_block_copy = copy.deepcopy(def_blocks)
            for label in def_block_copy:
                for block in dominance_frontier[label]:
                    if block not in phi_blocks:
                        phi_blocks[block] = set()
                    phi_blocks[block].add(variable)
                    defs[variable].add(block)
        return phi_blocks
    
    @staticmethod
    def rename_variables(cfg: CFG, phi_blocks: dict, defs: dict, dominance_tree: dict) -> dict:      
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
            for instruction in block.instructions:
                if 'args' in instruction:
                    instruction["args"] = [stack[arg][-1] if arg in stack else arg for arg in instruction["args"]]
                if 'dest' in instruction:
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
            
            if block_name in dominance_tree:
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