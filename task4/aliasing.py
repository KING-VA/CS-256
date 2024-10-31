# Aliasing Analysis and Dead store elimination code
import json
import sys
import copy
import click

from cfg import CFG

import logging
logging.basicConfig(level=logging.WARNING, filename='pass_processor.log')
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
    def __init__(self, cfg_class: CFG):
        self.cfg_class = cfg_class
        self.cfg = cfg_class.cfg

    @staticmethod
    def merge_fn(inputs: list[dict]) -> dict:
        """ Merge function for the alias analysis algorithm """
        input_copy = copy.deepcopy(inputs)
        keys = input_copy[0].keys()
        output = dict()
        for key in keys:
            output[key] = set.union(*input_copy[key])
        return output
    
    @staticmethod
    def transfer_fn(block, inputs: dict) -> dict:
        """ Transfer function for the alias analysis algorithm """
        memory_set = copy.deepcopy(inputs)
        for instr in block.instructions:
            if 'op' in instr:
                if instr['op'] == 'alloc':
                    memory_set[instr['dest']] = set([instr['value']])
                elif instr['op'] == 'id' or instr['op'] == 'ptradd':
                    if instr['value'] in memory_set:
                        memory_set[instr['dest']] = memory_set[instr['value']]
                elif instr['op'] == 'load':
                    memory_set[instr['dest']] = set([instr['value']])
        return memory_set

    
    @staticmethod
    def worklist_algorithm(cfg, merge_fn, transfer_fn, reverse, debug=False) -> tuple:
        """ Perform the worklist algorithm given the current CFG, merge function, and transfer function """
        inputs = dict()
        outputs = dict()
        for label in cfg:
            inputs[label] = dict()
            outputs[label] = set()
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
                print(f"Processed block {label}")
                print(f"Worklist: {list(worklist.keys())}")
                print(f"Inputs: {inputs}")
                print(f"Outputs: {outputs}")

        if debug:
            AliasAnalysis.print_inputs_outputs(inputs, outputs, reverse=reverse)
        return (inputs, outputs)
    
    def print_inputs_outputs(inputs, outputs, reverse=False):
        """ Print the inputs and outputs for debugging """
        def print_helper(set_dict):
            if len(set_dict) == 0:
                print("∅")
            else:
                list_set = list(set_dict)
                list_set.sort()
                for idx, value in enumerate(list_set):
                    if idx == len(list_set) - 1:
                        print(value)
                    else:
                        print(value, end=", ")

        for key in inputs.keys():
            print(f"{key}:")
            if reverse:
                print("\tin:\t", end="")
                print_helper(outputs[key])
                print("\tout:\t", end="")
                print_helper(inputs[key])
            else:
                print("\tin:\t", end="")
                print_helper(inputs[key])
                print("\tout:\t", end="")
                print_helper(outputs[key])
    


# def dead_store_elimination(instructions, debug=False) -> list:
#     """ Perform Dead Store Elimination on the function's instructions and return the optimized instructions """
#     all_mem_locations = "all_mem_locations"
#     reverse_analysis = False
#     cfg_class = CFG.create_cfg_from_function(instructions, reverse=reverse_analysis)
#     cfg = cfg_class.cfg
#     # Compute the input variables for the function and have the input variables 
#     defs, types, uses, input_variables_dict = SSA.get_defs_uses_types_inputs(cfg)
#     input_variables = set([var for var in input_variables_dict if input_variables_dict[var]])
    
#     # Create state mapping for the tracking of all variables and their memory locations
#     state_dict = dict()

#     # Initialize the state for the input variables to the function
#     for input_var in input_variables:
#         state_dict[input_var] = set([all_mem_locations])

#     def merge_fn(inputs) -> set:
#         """ Merge function for the worklist algorithm """
#         if not inputs:
#             return set()
#         return set.union(*inputs)
    
#     for analysis_variable in defs:
#         def transfer_fn(block, inputs, currentVariable=analysis_variable) -> set:
#             """ Transfer function for the worklist algorithm """
#             memorySet = copy.deepcopy(inputs) 
#             instructions = copy.deepcopy(block.instructions)
#             for instr in instructions:
#                 if 'op' in instr:
#                     if instr['op'] == 'alloc' and instr['dest'] == currentVariable:
#                         memorySet.add(instr['value'])
#                     elif instr['op'] == 'id' or instr['op'] == 'ptradd':
#                         if instr['value'] == currentVariable:
#                             add_to_set(instr['dest'], instr['value'], memorySet)
#                     elif instr['op'] == 'load':
#                         add_to_set(instr['dest'], all_mem_locations, memorySet)
                    
#             return memorySet
        
#         inputSet, outputSet = WorkListPasses.worklist_algorithm(cfg, merge_fn, transfer_fn, reverse_analysis, debug=debug)

#     # Remove dead stores from the CFG
#     cfg_copy = copy.deepcopy(cfg)
#     for label, block in cfg_copy.items():
#         actual_block = cfg[label]
#         for idx, instr in enumerate(block.instructions):
#             if 'op' in instr and instr['op'] == 'store' and instr['dest'] in inputSet[label] and instr['value'] in inputSet[label]:
#                 actual_block.instructions.remove(instr)

@click.command()
@click.option('--debug', 'is_debug', is_flag=True, default=False, help='Debug Flag')
def main(is_debug):
    """ Main function for alias analysis processor -- similar structure to the pass processor but more generalized for alias analysis """
    prog = json.load(sys.stdin)
    logging.info("Starting Alias Analysis for Dead Store Elimination")
    for fn in prog["functions"]:
        cfg = CFG.create_cfg_from_function(fn['instrs'])
        instr = AliasAnalysis.dead_store_elimination(cfg, fn['instrs'], debug=is_debug)
        fn['instrs'] = instr
    json.dump(prog, sys.stdout, indent=2)

if __name__ == "__main__":
    main()