import json
import sys
from typing_extensions import Self, Dict
import copy
import graphviz

from basic_blocks import BasicBlock

class DominanceTree(object):
    def __init__(self, name):
        self.name = name
        self.pred = []
        self.succ = []

class CFG(object):
    """
    Create a control flow graph from a list of basic blocks
    """
    DEFAULT_START_LABEL = "start_cfg"
    DEFAULT_END_LABEL = "end_cfg"

    def __init__(self, basic_blocks, reverse=False):
        self.reverse = reverse
        self.cfg = CFG.build_cfg(basic_blocks, reverse)
        self.dominators = self.compute_dominators()
        self.dominance_frontiers = self.compute_dominance_frontiers()
        self.dominance_tree = self.build_dominance_tree()
        self.back_edges = self.compute_back_edges()
        self.reducible = self.is_reducible()

    @property
    def edges(self):
        edges = set()
        for label, block in self.cfg.items():
            for succ in block.succ:
                edges.add((label, succ))
        return edges
    
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
    
    def compute_dominators(self) -> Dict[str, set]:
        dominators = dict()
        for label in self.cfg:
            dominators[label] = set()
        dominators[CFG.DEFAULT_START_LABEL].add(CFG.DEFAULT_START_LABEL)
        changed = True
        while changed:
            changed = False
            for label in self.cfg:
                if label == CFG.DEFAULT_START_LABEL:
                    continue
                predecessor_dom = [dominators[pred] for pred in self.cfg[label].pred if pred in dominators]
                new_dominators = set.intersection(*predecessor_dom) if predecessor_dom else set()
                new_dominators.add(label)
                if new_dominators != dominators[label]:
                    changed = True
                    dominators[label] = new_dominators
        return dominators
    
    def compute_dominance_frontiers(self) -> Dict[str, set]:
        dominance_frontiers = dict()
        for label in self.cfg:
            dominance_frontiers[label] = set()
            dominated_blocks = {vertex for vertex, doms in self.dominators.items() if label in doms}
            for vertex in dominated_blocks:
                for succ in self.cfg[vertex].succ:
                    if succ not in dominated_blocks or label == succ:
                        dominance_frontiers[label].add(succ)
        return dominance_frontiers
    
    def build_dominance_tree(self) -> Dict[str, set]:
        dominance_tree = dict()
        for label in self.cfg:
            dominators = copy.deepcopy(self.dominators[label])
            dominators.remove(label)
            immediate_dominator = set()
            for dom in dominators:
                dom_set = {vertex for vertex, doms in self.dominators.items() if dom in doms}
                if all(dom2 == dom or dom2 not in dom_set for dom2 in dominators):
                    immediate_dominator.add(dom)
            for node in immediate_dominator:
                if label not in dominance_tree:
                    dominance_tree[label] = DominanceTree(label)
                if node not in dominance_tree:
                    dominance_tree[node] = DominanceTree(node)
                dominance_tree[node].succ.append(label)
                dominance_tree[label].pred.append(node)
        return dominance_tree
    
    def compute_back_edges(self) -> set:
        backedges = set()
        for node, doms in self.dominators.items():
            for dom in doms:
                if (node, dom) in self.edges:
                    backedges.add((node, dom))
        return backedges
    
    def is_reducible(self) -> bool:
        cfg_edges = copy.deepcopy(self.edges)

        for tail, header in self.back_edges:
            cfg_edges.remove((tail, header))
        
        visited = set()
        stack = set()

        def is_cyclic(node) -> bool:
            visited.add(node)
            stack.add(node)
            for source, dest in cfg_edges:
                if source == node:
                    if dest not in visited:
                        if is_cyclic(dest):
                            return True
                    elif dest in stack:
                        return True
            stack.remove(node)
            return False
        
        return not is_cyclic(CFG.DEFAULT_START_LABEL)
    
    def get_loop_information(self, backedge) -> dict:
        tail, header = backedge
        cfg_edges = copy.deepcopy(self.edges)
        for source, dest in self.back_edges:
            if dest == header:
                cfg_edges.remove((source, dest))
            if source == header:
                cfg_edges.remove((source, dest))

        nodes = set()
        new_nodes = {tail}
        while nodes != new_nodes:
            nodes = copy.deepcopy(new_nodes)
            for node in nodes:
                new_nodes.update({source for source, dest in cfg_edges if dest == node})
        nodes.add(header)
        return {'backedge' : backedge, 'header': header, 'nodes' : nodes}

    def reachable(self, source, dest) -> bool:
        visited = set()
        stack = [source]
        while stack:
            node = stack.pop()
            if node == dest:
                return True
            visited.add(node)
            for succ in self.cfg[node].succ:
                if succ not in visited:
                    stack.append(succ)
        return False

    def get_cfg_instruction_list(self, debug=False) -> list:
        return CFG.instructions_from_cfg(self.cfg, debug=debug)
    
    @staticmethod
    def instructions_from_cfg(cfg, debug=False) -> list:
        instrs = list()
        for label, block in cfg.items():
            if debug:
                instrs.append({'label' : ''+ label +'_cfg'})
            instrs.extend(block.instructions)
        return instrs
    
    def plot_cfg(self, start_label):
        dot = self.generate_graphviz(start_label)
        dot.render('cfg', format='png', cleanup=True)

    def plot_dominance_tree(self):
        dot = graphviz.Digraph()
        for vertex in self.dominance_tree:
            dot.node(vertex, vertex=vertex)
        for vertex, tree in self.dominance_tree.items():
            for succ in tree.succ:
                dot.edge(vertex, succ)
        dot.render('dominance_tree', format='png', cleanup=True)

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
    def create_cfg_from_function(instructions, reverse=False, debug=False) -> Self:
        blocks = BasicBlock.create_blocks_from_function(instructions)
        if debug:
            for block in blocks:
                print(block)
        return CFG(blocks, reverse=reverse)

def main():
    prog = json.load(sys.stdin)
    for fn in prog["functions"]:
        cfg = CFG.create_cfg_from_function(fn['instrs'])
        cfg.plot_cfg(CFG.DEFAULT_START_LABEL)

if __name__ == "__main__":
    main()