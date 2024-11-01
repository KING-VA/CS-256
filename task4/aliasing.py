# Aliasing Analysis and Dead store elimination code
import json
import sys
import copy
import click

from cfg import CFG
from ssa import SSA

import logging
logging.basicConfig(level=logging.WARNING, filename='aliasing.log')
logger = logging.getLogger(__name__)

class AliasAnalysis(object):
    """
    While alloc is the only way to create a memory location from nothing, there are other ways to create memory locations, and these are the sources of aliasing.

        p1 = id p2: the move or copy instruction is the most obvious way to create an alias.
        p1 = ptradd p2 offset: pointer arithmetic is an interesting and challenging source of aliasing. To figure out if these two pointers can alias, we'd need to figure out if offset can be zero. To simplify things, we will assume that offset could always be zero, and so we will conservatively say that p1 and p2 can alias. This also means we do not need to include indexing informations into our represetation of memory locations.
        p1 = load p2: you can have pointers to other pointers, and so loading a pointer effectively copy a pointer, creating an alias.

    Our dataflow analysis will center around building the points-to graph, a structure that maps each variable to the set of memory locations it can point to.

    Here is a first, very conservative stab at it:

        Direction: forward
        State: map of var -> set[memory location]
            If two vars have a non-empty intersection, they might alias!
        Meet: Union for each variable's set of memory locations
        Transfer function:
            x = alloc n: x points to this allocations
            x = id y: x points to the same locations as y did
            x = ptradd p offset: same as id (conservative)
            x = load p: we aren't tracking anything about p, so x points to all memory locations
            store p x: no change

    """
    ALL_MEM_LOCATIONS = "all_mem_locations"

    def __init__(self, cfg_class: CFG, input_variables_dict: dict, debug=False):
        """ Initialize the AliasAnalysis object """
        self.cfg_class = cfg_class
        self.cfg = cfg_class.cfg
        self.input_variables_dict = input_variables_dict
        self.input_variables = dict()
        for var in input_variables_dict:
            if input_variables_dict[var]:
                self.input_variables[var] = set([AliasAnalysis.ALL_MEM_LOCATIONS])
        
        # Run the worklist algorithm to compute the points-to graph
        self.inputs, self.outputs = AliasAnalysis.worklist_algorithm(self.cfg, AliasAnalysis.merge_fn, AliasAnalysis.transfer_fn, reverse=False, debug=debug, starting_input=self.input_variables)
        # Use the points-to graph to perform alias analysis --> returning a dictionary of variables that contain of set of variables that they may alias with
        self.alias_analysis = AliasAnalysis.compute_alias_analysis(self.outputs)

        if debug:
            logging.debug("Alias Analysis:")
            logging.debug(self.alias_analysis)

    @staticmethod
    def dead_store_elimination(cfg: CFG, debug=False) -> list:
        """ Perform Dead Store Elimination on the function's instructions and return the optimized instructions """
        # Compute the input variables
        defs, types, uses, input_variables_dict = SSA.get_defs_uses_types_inputs(cfg)
        
        # Compute the alias analysis
        alias_analysis_class = AliasAnalysis(cfg, input_variables_dict, debug=debug)
        alias_analysis = alias_analysis_class.alias_analysis

        # Get instructions from the CFG
        cfg_instructions = cfg.get_cfg_instruction_list()
        cfg_instructions_copy = copy.deepcopy(cfg_instructions)

        # Remove dead stores from the CFG
        for idx_1, instr in enumerate(cfg_instructions):
            # Check to see that the original variable and any aliases are not being used
            if 'op' in instr and instr['op'] == 'store':
                can_remove = True
                for instr2 in cfg_instructions[idx_1+1:]:
                    if 'args' in instr2:
                        for arg in instr2['args']:
                            if instr['dest'] == arg or arg in alias_analysis[instr['dest']]:
                                can_remove = False
                                break
                if can_remove:
                    if debug:
                        logging.debug(f"Removing dead store: {instr}")
                    cfg_instructions_copy.remove(instr)
        if debug:
            logging.info("Dead Store Elimination Complete")
        return cfg_instructions_copy
             
    @staticmethod
    def compute_alias_analysis(state_mapping: dict) -> dict:
        """ Compute the alias analysis from the outputs of the worklist algorithm
                Input: Dict mapping variable to memory region
                Output: Dict mapping variable to their aliases (Using intersection of memory regions to find aliases)
        """
        alias_analysis = dict()
        for var in state_mapping:
            alias_analysis[var] = set()
            for other_var in state_mapping:
                if var != other_var and state_mapping[var].intersection(state_mapping[other_var]) or AliasAnalysis.ALL_MEM_LOCATIONS in var or AliasAnalysis.ALL_MEM_LOCATIONS in other_var:
                    alias_analysis[var].add(other_var)
        return alias_analysis

    @staticmethod
    def merge_fn(inputs: list[dict]) -> dict:
        """ Merge function for the alias analysis algorithm """
        inputs_copy = copy.deepcopy(inputs)
        output = dict()
        for key in inputs_copy[0].keys():
            output[key] = set.union(*[inputs[key] for inputs in inputs_copy])
        return output
    
    @staticmethod
    def transfer_fn(block, inputs: dict) -> dict:
        """ Transfer function for the alias analysis algorithm """
        def add_to_set(dest, value, state_mapping):
            if dest in state_mapping:
                state_mapping[dest].add(value)
            else:
                state_mapping[dest] = set([value])
            return state_mapping

        state_mapping = copy.deepcopy(inputs)
        for instr in block.instructions:
            if 'op' in instr:
                dest = instr['dest']
                # value = instr['value']
                if instr['op'] == 'alloc':
                    add_to_set(dest, instr['value'], state_mapping)
                elif (instr['op'] == 'id' or instr['op'] == 'ptradd'):
                    if instr['args'][0] in state_mapping:
                        add_to_set(dest, instr['args'][0], state_mapping)
                elif instr['op'] == 'load':
                    add_to_set(dest, AliasAnalysis.ALL_MEM_LOCATIONS, state_mapping)

        return state_mapping

    @staticmethod
    def worklist_algorithm(cfg, merge_fn, transfer_fn, reverse, debug=False, starting_input:dict=None) -> tuple:
        """ Perform the worklist algorithm given the current CFG, merge function, and transfer function """
        inputs = dict()
        outputs = dict()
        for label in cfg:
            inputs[label] = dict() if starting_input is None else starting_input
            outputs[label] = dict()
        worklist = copy.deepcopy(cfg)
        while worklist:
            label = list(worklist.keys())[0]
            block = worklist.pop(label)

            block_inputs = [outputs[pred] for pred in block.pred]
            inputs[label] = merge_fn(block_inputs)
            
            block_outputs = transfer_fn(block, inputs[label])

            cfg[label].instructions = block.instructions

            if len(block_outputs) != len(outputs[label]):
                outputs[label] = block_outputs
                for succ in block.succ:
                    worklist[succ] = cfg[succ]

            if debug:
                logging.debug(f"Processed block {label}")
                logging.debug(f"Worklist: {list(worklist.keys())}")
                logging.debug(f"Inputs: {inputs}")
                logging.debug(f"Outputs: {outputs}")

        if debug:
            AliasAnalysis.print_inputs_outputs(inputs, outputs, reverse=reverse)
        return (inputs, outputs)
    
    def print_inputs_outputs(inputs, outputs, reverse=False):
        """ Print the inputs and outputs for debugging """
        def print_helper(set_dict):
            if len(set_dict) == 0:
                logging.debug("∅")
            else:
                list_set = list(set_dict)
                list_set.sort()
                for idx, value in enumerate(list_set):
                    if idx == len(list_set) - 1:
                        logging.debug(value)
                    else:
                        logging.debug(value, end=", ")

        for key in inputs.keys():
            logging.debug(f"{key}:")
            if reverse:
                logging.debug("\tin:\t", end="")
                print_helper(outputs[key])
                logging.debug("\tout:\t", end="")
                print_helper(inputs[key])
            else:
                logging.debug("\tin:\t", end="")
                print_helper(inputs[key])
                logging.debug("\tout:\t", end="")
                print_helper(outputs[key])

@click.command()
@click.option('--debug', 'is_debug', is_flag=True, default=False, help='Debug Flag')
def main(is_debug):
    """ Main function for alias analysis processor -- similar structure to the pass processor but more generalized for alias analysis """
    prog = json.load(sys.stdin)
    logging.info("Starting Alias Analysis for Dead Store Elimination")
    for fn in prog["functions"]:
        cfg = CFG.create_cfg_from_function(fn['instrs'])
        instr = AliasAnalysis.dead_store_elimination(cfg, debug=is_debug)
        fn['instrs'] = instr
    json.dump(prog, sys.stdout, indent=2)

if __name__ == "__main__":
    main()