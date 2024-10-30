import json
import sys
import click
import copy

from cfg import CFG
from lvn import LocalValueNumbering
from basic_blocks import BasicBlock

class WorkListPasses(object):
    """
    A worklist class to help process the different passes on the CFG
    """
    @staticmethod
    def liveness_analysis(instructions, debug=False) -> list:
        """ Perform Liveness Analysis on the function's instructions and return the optimized instructions after global dead code elimination """
        reverse_analysis = True
        cfg_class = CFG.create_cfg_from_function(instructions, reverse=reverse_analysis)
        cfg = cfg_class.cfg
        def merge_fn(inputs) -> set:
            """ Merge function for the worklist algorithm """
            if not inputs:
                return set()
            return set.union(*inputs)
        
        def transfer_fn(block, inputs) -> set:
            """ Transfer function for the worklist algorithm """
            # Here in is out and out is in due to the reverse being done in the CFG generation (See the CFG class for this)
            alive = copy.deepcopy(inputs)
            instructions = copy.deepcopy(block.instructions)
            instructions.reverse()
            for instr in instructions:
                if 'dest' in instr and instr['dest'] in alive:
                    alive.remove(instr['dest'])
                if 'args' in instr:
                    for arg in instr['args']:
                        alive.add(arg)
            return alive
        
        inputSet, outputSet = WorkListPasses.worklist_algorithm(cfg, merge_fn, transfer_fn, reverse_analysis, debug=debug)
        
        # Remove the dead code from the CFG
        cfg_copy = copy.deepcopy(cfg)
        for label, block in cfg_copy.items():
            actual_block = cfg[label]
            for idx, instr in enumerate(block.instructions):
                if 'dest' in instr and instr['dest'] not in inputSet[label]:
                    # Need to run a pass of dead code here to verify that the instruction is not used in the block, if it is, then we cannot remove it
                    can_remove = True
                    for instr2 in block.instructions[idx+1:]:
                        if 'args' in instr2:
                            for arg in instr2['args']:
                                if instr['dest'] == arg:
                                    can_remove = False
                                    break
                    if can_remove:
                        actual_block.instructions.remove(instr)

            # Remove the block if it has no instructions and link the predecessors and successors together before removing it from the CFG
            if not actual_block.instructions:
                for pred in actual_block.pred:
                    for succ in actual_block.succ:
                        pred.add_successor(succ)
                    pred.remove_successor(label)
                for succ in actual_block.succ:
                    for pred in actual_block.pred:
                        succ.add_predecessor(pred)
                    succ.remove_predecessor(label)
                cfg.pop(label)

        return cfg_class.get_cfg_instruction_list(debug=debug)
    
    @staticmethod
    def local_value_numbering(instructions, debug=False) -> list:
        """ Perform Global Value Numbering on the function's instructions and return the optimized instructions """
        reverse_analysis = False
        cfg_class = CFG.create_cfg_from_function(instructions, reverse=reverse_analysis)
        cfg = cfg_class.cfg
        def merge_fn(inputs) -> set:
            """ Merge function for the worklist algorithm """
            if not inputs:
                return set()
            return set.intersection(*inputs)
        
        def transfer_fn(block, inputs) -> set:
            """ Transfer function for the worklist algorithm """
            lvn = LocalValueNumbering()
            instructions = lvn.pass_block(block.instructions, inputs)
            block.instructions = instructions
            outputSet = set()
            for instr in instructions:
                if 'dest' not in instr:
                    continue
                if 'op' not in instr:
                    continue
                if 'args' in instr:
                    value_tuple = (instr['op'], instr['dest'], *instr['args'])
                else:
                    value_tuple = (instr['op'], instr['dest'], instr['value'])
                outputSet.add(value_tuple)
            return outputSet

        inputSet, outputSet = WorkListPasses.worklist_algorithm(cfg, merge_fn, transfer_fn, reverse_analysis, debug=debug)
        return cfg_class.get_cfg_instruction_list(debug=debug)

    @staticmethod
    def worklist_algorithm(cfg, merge_fn, transfer_fn, reverse, debug=False) -> tuple:
        """ Perform the worklist algorithm given the current CFG, merge function, and transfer function """
        inputs = dict()
        outputs = dict()
        for label in cfg:
            inputs[label] = set()
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
            WorkListPasses.print_inputs_outputs(inputs, outputs, reverse=reverse)
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

@click.command()
@click.option('--liveness', 'is_liveness', is_flag=True, default=False, help='Liveness Analysis Flag')
@click.option('--local_value_numbering', 'is_local_value_numbering', is_flag=True, default=False, help='Local Value Numbering Flag')
@click.option('--debug', 'is_debug', is_flag=True, default=False, help='Debug Flag')
def main(is_liveness, is_local_value_numbering, is_debug):
    """ Main function for CFG Processor -- parses input and calls the appropriate pass """
    prog = json.load(sys.stdin)
    for fn in prog["functions"]:
        if is_liveness:
            instr = WorkListPasses.liveness_analysis(fn['instrs'], debug=is_debug)
        elif is_local_value_numbering:
            instr = WorkListPasses.local_value_numbering(fn['instrs'], debug=is_debug)
        fn['instrs'] = instr

    json.dump(prog, sys.stdout, indent=2)

if __name__ == "__main__":
    main()