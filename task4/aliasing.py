# Aliasing Analysis and Dead store elimination code
import json
import sys
import copy
import click

from cfg import CFG
from ssa import SSA

import logging
logging.basicConfig(filename='aliasing.log', level=logging.WARNING)
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
        self.unique_loc_num = 0
        self.cfg_class = cfg_class
        self.cfg = cfg_class.cfg
        self.input_variables_dict = input_variables_dict
        self.input_variables = dict()
        for var in input_variables_dict:
            if input_variables_dict[var]:
                self.input_variables[var] = set([AliasAnalysis.ALL_MEM_LOCATIONS])
        if debug:
            logger.debug("Input Variables:")
            logger.debug(self.input_variables)
        # Run the worklist algorithm to compute the points-to graph
        self.inputs, self.outputs, self.final_output = AliasAnalysis.worklist_algorithm(self.cfg, self.merge_fn, self.transfer_fn, reverse=False, debug=debug, starting_input=self.input_variables)
        if debug:
            logger.debug("Final Output:")
            logger.debug(self.final_output)
            logger.debug("Outputs:")
            logger.debug(self.outputs)
            logger.debug("Inputs:")
            logger.debug(self.inputs)
        # Use the points-to graph to perform alias analysis --> returning a dictionary of variables that contain of set of variables that they may alias with
        self.alias_analysis = AliasAnalysis.compute_alias_analysis(self.final_output)
        if debug:
            logger.debug("Alias Analysis:")
            logger.debug(self.alias_analysis)

    def get_unique_loc_num(self):
        """ Get a unique location number for a memory location """
        self.unique_loc_num += 1
        return self.unique_loc_num
    
    def merge_fn(self, inputs: list[dict]) -> dict:
        """ Merge function for the alias analysis algorithm """
        if not inputs or len(inputs) == 0:
            return dict()
        output = dict()
        logger.debug(f"Merge Inputs: {inputs}")
        for key in inputs[0].keys():
            output[key] = set.union(*[input[key] for input in inputs if key in input])
        return output

    def transfer_fn(self, block, inputs: dict) -> dict:
        """ Transfer function for the alias analysis algorithm """
        def add_to_set(dest, value, state_mapping):
            if type(value) is not set:
                value = set([value])
            if dest in state_mapping:
                for val in value:
                    state_mapping[dest].add(val)
            else:
                state_mapping[dest] = set(value)
            return state_mapping

        state_mapping = copy.deepcopy(inputs)
        for instr in block.instructions:
            if 'op' in instr:
                if instr['op'] == 'alloc':
                    logging.debug(f"Allocating {instr['dest']}: {instr}")
                    add_to_set(instr['dest'], self.get_unique_loc_num(), state_mapping)
                elif (instr['op'] == 'id' or instr['op'] == 'ptradd'):
                    logging.debug(f"Copying {instr['args'][0]} to {instr['dest']}: {instr}")
                    if instr['args'][0] in state_mapping:
                        add_to_set(instr['dest'], state_mapping[instr['args'][0]], state_mapping)
                elif instr['op'] == 'load':
                    logging.debug(f"Loading {instr['args'][0]} to {instr['dest']}: {instr}")
                    add_to_set(instr['dest'], AliasAnalysis.ALL_MEM_LOCATIONS, state_mapping)

        return state_mapping

    @staticmethod
    def dead_store_elimination(cfg: CFG, debug=False) -> list:
        """ Perform Dead Store Elimination on the function's instructions and return the optimized instructions """
        def remove_variable_and_aliases(alias_analysis, variable, last_store) -> dict:
            aliases = alias_analysis.get(instr['args'][0], set())
            last_store.pop(variable, None)
            for alias in aliases:
                last_store.pop(alias, None)
            if AliasAnalysis.ALL_MEM_LOCATIONS in aliases:
                last_store = dict()
            return last_store

        # Compute the input variables
        defs, types, uses, input_variables_dict = SSA.get_defs_uses_types_inputs(cfg)
        
        # Compute the alias analysis
        alias_analysis_class = AliasAnalysis(cfg, input_variables_dict, debug=debug)
        alias_analysis = alias_analysis_class.alias_analysis

        # Get instructions from the CFG
        cfg_instructions = cfg.get_cfg_instruction_list()
        cfg_instructions_copy = copy.deepcopy(cfg_instructions)

        # Remove dead stores from the CFG
        last_store = dict()
        for idx, instr in enumerate(cfg_instructions):
            if 'op' in instr:
                if instr['op'] == 'ptradd' and instr['dest'] in last_store:
                    # For each ptradd, if the variable is being changed, remove the variable from the last store dictionary since it is being modified so the variable matching doesn't mean anything (here we aren't checking what the offset and default removal to be more conservative)
                    last_store = remove_variable_and_aliases(alias_analysis, instr['dest'], last_store)
                elif instr['op'] == 'load':
                    # For each load, remove the variable from the last store dictionary since it is being used (here use the alias analysis to be more conservative)
                    last_store = remove_variable_and_aliases(alias_analysis, instr['args'][0], last_store)
                elif instr['op'] == 'store':
                    # For each store check to see if the variable is being overwritten -- convervatively only remove if it is the same variable (no alias)
                    if instr['args'][0] in last_store:
                        if debug:
                            logger.debug(f"Removing dead store: {instr}")
                        cfg_instructions_copy.remove(instr)
                    else:
                        logger.debug(f"Adding Store: {instr}")
                        last_store[instr['args'][0]] = idx

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
                if var != other_var and (state_mapping[var].intersection(state_mapping[other_var]) or AliasAnalysis.ALL_MEM_LOCATIONS in state_mapping[var] or AliasAnalysis.ALL_MEM_LOCATIONS in state_mapping[other_var]):
                    alias_analysis[var].add(other_var)
            if AliasAnalysis.ALL_MEM_LOCATIONS in state_mapping[var]:
                alias_analysis[var].add(AliasAnalysis.ALL_MEM_LOCATIONS)

        return alias_analysis

    @staticmethod
    def worklist_algorithm(cfg, merge_fn, transfer_fn, reverse, debug=False, starting_input:dict=None) -> tuple:
        """ Perform the worklist algorithm given the current CFG, merge function, and transfer function """
        inputs = dict()
        outputs = dict()
        for label in cfg:
            inputs[label] = dict()
            outputs[label] = dict()
        worklist = copy.deepcopy(cfg)
        final_outputs = None
        while worklist:
            label = list(worklist.keys())[0]
            block = worklist.pop(label)
            
            if label == CFG.DEFAULT_START_LABEL and starting_input:
                block_inputs = [starting_input]
            else:
                block_inputs = [outputs[pred] for pred in block.pred]
            inputs[label] = merge_fn(block_inputs)
            
            block_outputs = transfer_fn(block, inputs[label])

            cfg[label].instructions = block.instructions

            if len(block_outputs) != len(outputs[label]):
                outputs[label] = block_outputs
                for succ in block.succ:
                    worklist[succ] = cfg[succ]
                final_outputs = block_outputs

            if debug:
                logger.debug(f"Processed block {label}")
                logger.debug(f"Worklist: {list(worklist.keys())}")
                logger.debug(f"Inputs: {inputs}")
                logger.debug(f"Outputs: {outputs}")

        if False: # debug:
            AliasAnalysis.print_inputs_outputs(inputs, outputs, reverse=reverse)
        return (inputs, outputs, final_outputs)
    
    def print_inputs_outputs(inputs, outputs, reverse=False):
        """ Print the inputs and outputs for debugging """
        def print_helper(set_dict):
            if len(set_dict) == 0:
                logger.debug("∅")
            else:
                list_set = list(set_dict)
                list_set.sort()
                for idx, value in enumerate(list_set):
                    if idx == len(list_set) - 1:
                        logger.debug(value)
                    else:
                        logger.debug(f"{value}, ")

        for key in inputs.keys():
            logger.debug(f"{key}:")
            if reverse:
                logger.debug("\tin:\t")
                print_helper(outputs[key])
                logger.debug("\tout:\t")
                print_helper(inputs[key])
            else:
                logger.debug("\tin:\t")
                print_helper(inputs[key])
                logger.debug("\tout:\t")
                print_helper(outputs[key])

@click.command()
@click.option('--debug', 'is_debug', is_flag=True, default=False, help='Debug Flag')
def main(is_debug):
    """ Main function for alias analysis processor -- similar structure to the pass processor but more generalized for alias analysis """
    prog = json.load(sys.stdin)
    logger.info("Starting Alias Analysis for Dead Store Elimination")
    for fn in prog["functions"]:
        cfg = CFG.create_cfg_from_function(fn['instrs'])
        instr = AliasAnalysis.dead_store_elimination(cfg, debug=is_debug)
        fn['instrs'] = instr
    logger.info(f"Dead Store Elimination Complete")
    json.dump(prog, sys.stdout, indent=2)

if __name__ == "__main__":
    main()