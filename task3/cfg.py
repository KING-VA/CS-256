import json
import sys
from typing_extensions import Self, Dict
import graphviz

from basic_blocks import BasicBlock

class CFG(object):
    """
    Create a control flow graph from a list of basic blocks
    """
    DEFAULT_START_LABEL = "start"
    DEFAULT_END_LABEL = "end"

    def __init__(self, basic_blocks, reverse=False):
        self.reverse = reverse
        self.cfg = CFG.build_cfg(basic_blocks, reverse)
    
    @staticmethod
    def build_cfg(basic_blocks, reverse) -> Dict[str, BasicBlock]:
        cfg = dict()

        # Setup add_to_successor and add_to_predecessor functions
        if reverse:
            add_to_successor = lambda block, target: block.add_predecessor(target)
            add_to_predecessor = lambda block, target: block.add_successor(target)
        else:
            add_to_successor = lambda block, target: block.add_successor(target)
            add_to_predecessor = lambda block, target: block.add_predecessor(target)

        for block in basic_blocks:
            # Assume that the block is the start node if it doesn't have a label
            label = CFG.DEFAULT_START_LABEL
            first_instr = block.instructions[0]
            if "label" in first_instr:
                label = first_instr['label']
            cfg[label] = block

        for label, block in cfg.items():
            last_instr = block.instructions[-1]
            last_instr_op = last_instr['op']
            
            if last_instr_op == "jmp":
                jmp_target = last_instr['labels'][0]
                add_to_successor(block, jmp_target)
                add_to_predecessor(cfg[jmp_target], label)
            elif last_instr_op == "br":
                br_targets = last_instr['labels']
                for target in br_targets:
                    add_to_successor(block, target)
                    add_to_predecessor(cfg[target], label)
            else:
                # This is a label divsion so just add the next block as a successor
                index_curr_block = basic_blocks.index(block)
                index_next_block = index_curr_block + 1
                if index_next_block < len(basic_blocks):
                    # Search the label of the next block in cgf
                    next_block_label = CFG.DEFAULT_END_LABEL
                    for label2, block2 in cfg.items():
                        if block2 == basic_blocks[index_next_block]:
                            next_block_label = label2
                            break
                    add_to_successor(block, next_block_label)
                    add_to_predecessor(cfg[next_block_label], label)
        return cfg

    def get_cfg_instruction_list(self, debug=False) -> list:
        instrs = list()
        for label, block in self.cfg.items():
            if debug:
                instrs.append({'label' : ''+ label +'_cfg'})
            instrs.extend(block.instructions)
        return instrs
    
    def plot_cfg(self, start_label):
        dot = self.generate_graphviz(start_label)
        dot.render('cfg', format='png', cleanup=True)

    def generate_graphviz(self, start_label) -> graphviz.Digraph:
        dot = graphviz.Digraph()
        visited = set()
        queue = [start_label]
        while queue:
            label = queue.pop(0)
            if label in visited:
                continue
            visited.add(label)
            block = self.cfg[label]
            dot.node(label, label=label)
            for succ in block.succ:
                queue.append(succ)
                dot.edge(label, succ)
        return dot

    @staticmethod
    def create_cfg_from_function(instructions, reverse=False) -> Self:
        blocks = BasicBlock.create_blocks_from_function(instructions)
        return CFG(blocks, reverse=reverse)

def main():
    prog = json.load(sys.stdin)
    for fn in prog["functions"]:
        cfg = CFG.create_cfg_from_function(fn['instrs'])
        cfg.plot_cfg(CFG.DEFAULT_START_LABEL)

if __name__ == "__main__":
    main()