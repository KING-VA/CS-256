import sys
import json
from basic_blocks import BasicBlock
from bril_constants import TERMINATING_INSTRUCTIONS, COMMUTATIVE_OPERATIONS, SPECIAL_OPERATIONS

class LocalValueNumbering:
    """Class to perform Local Value Numbering."""
    
    def __init__(self):
        self.env = {}  # Symbol name -> local value number
        self.table = {}  # Local value numbering table
        self.tuples = []  # List of value tuples for bookkeeping
        self.unique_id = 0  # Unique ID counter

    def str_of_bool(self, value):
        """Convert boolean to string"""
        return 'true' if value else 'false'

    def compute(self, instr):
        """Try to compute the instruction. """
        if 'dest' not in instr or 'op' not in instr or instr['op'] in SPECIAL_OPERATIONS:
            return instr

        all_const_operands = False
        any_const_operands = False

        if 'args' in instr:
            if all(arg in self.env for arg in instr['args']):
                if instr['op'] == 'id':
                    return instr
                
                arg_nums = sorted(self.env[arg] for arg in instr['args'])
                # check to see if any of the arg_nums are strings, then bail out
                if any(isinstance(num, str) for num in arg_nums):
                    return instr
                const_operands = [self.tuples[num][0] == 'const' for num in arg_nums]
                all_const_operands = all(const_operands)
                any_const_operands = any(const_operands)
            else:
                arg_nums = instr['args']
                local_args = [self.env[arg] for arg in instr['args'] if arg in self.env]
                any_const_operands = any(self.tuples[num][0] == 'const' for num in local_args)
        else:
            return instr

        op = instr['op']
        const_instr = {'op': 'const', 'dest': instr['dest']}

        if all_const_operands:
            args = [self.tuples[num][1] for num in arg_nums]
            operations = {
                'ne': lambda x, y: self.str_of_bool(x != y),
                'eq': lambda x, y: self.str_of_bool(x == y),
                'le': lambda x, y: self.str_of_bool(x <= y),
                'lt': lambda x, y: self.str_of_bool(x < y),
                'gt': lambda x, y: self.str_of_bool(x > y),
                'ge': lambda x, y: self.str_of_bool(x >= y),
                'not': lambda x: self.str_of_bool(not x),
                'and': lambda x, y: self.str_of_bool(x and y),
                'or': lambda x, y: self.str_of_bool(x or y),
                'add': lambda x, y: x + y,
                'mul': lambda x, y: x * y,
                'sub': lambda x, y: x - y,
                'div': lambda x, y: x / y
            }

            if op in operations:
                value = operations[op](*args) if op not in ['not'] else operations[op](args[0])
                const_instr.update({'value': value, 'type': 'bool' if op in ['ne', 'eq', 'le', 'lt', 'gt', 'ge', 'not', 'and', 'or'] else 'int'})
                return const_instr

        elif any_const_operands:
            if op == 'and':
                for arg_name in instr['args']:
                    if arg_name in self.env:
                        value = self.tuples[self.env[arg_name]][1]
                        if value == False:
                            return {'op': 'const', 'dest': instr['dest'], 'value': self.str_of_bool(False), 'type': 'bool'}
            elif op == 'or':
                for arg_name in instr['args']:
                    if arg_name in self.env:
                        value = self.tuples[self.env[arg_name]][1]
                        if value == True:
                            return {'op': 'const', 'dest': instr['dest'], 'value': self.str_of_bool(True), 'type': 'bool'}

        elif len(set(instr['args'])) == 1:
            constant_values = {
                'ne': False,
                'eq': True,
                'le': True,
                'lt': False,
                'gt': False,
                'ge': True
            }
            if op in constant_values:
                return {'op': 'const', 'dest': instr['dest'], 'value': self.str_of_bool(constant_values[op]), 'type': 'bool'}

        return instr

    def is_overwritten(self, dest, instrs):
        """Check if the destination variable is overwritten in the list of instructions."""
        return any(instr.get('dest') == dest for instr in instrs)

    def process_block(self, block):
        """Perform Local Value Numbering for a given basic block."""
        new_block = []
        self.env = {}
        self.table = {}
        self.tuples = []

        for idx, instr in enumerate(block):
            old_name = None

            instr = self.compute(instr)

            if 'op' not in instr or instr['op'] == 'nop' or 'labels' in instr or instr['op'] in TERMINATING_INSTRUCTIONS or instr['op'] in SPECIAL_OPERATIONS:
                new_block.append(instr)
                continue

            # edge case id of variable into variable
            if instr['op'] == 'id' and instr['args'][0] == instr['dest']:
                continue
            
            if 'args' in instr:
                if all(arg in self.env for arg in instr['args']):
                    arg_nums = sorted(self.env[arg] for arg in instr['args'])
                    value_tuple = (instr['op'], *arg_nums)
                    instr['args'] = [self.table[self.env[arg]]['name'] for arg in instr['args']]
                else:
                    value_tuple = (instr['op'], *instr['args'])
            else:
                value_tuple = (instr['op'], instr['value'])

            if instr['op'] in COMMUTATIVE_OPERATIONS:
                args = sorted(value_tuple[1:])
                value_tuple = (instr['op'], *args)

            if value_tuple in self.tuples:
                num = self.tuples.index(value_tuple)
                entry = self.table[num]
                if entry['value_tuple'][0] != 'const':
                    instr.update({'op': 'id', 'args': [entry['name']]})
                else:
                    pass
                    # instr.update({'op': 'const', 'value': entry['value_tuple'][1]}) # Some conversion issue from bools and ints
            elif instr['op'] == "id":
                num = value_tuple[1]
                if num in self.table:
                    opcode = self.table[num]['value_tuple'][0]
                    if opcode == 'const':
                        instr.update({'op': 'const', 'value': self.table[num]['value_tuple'][1]})
            else:
                if 'dest' in instr:
                    self.tuples.append(value_tuple)
                    num = len(self.tuples) - 1
                    name = instr['dest'] if not self.is_overwritten(instr['dest'], block[idx+1:]) else f"lvn.{self.unique_id}"
                    if name != instr['dest']:
                        self.unique_id += 1
                        old_name = instr['dest']
                        instr['dest'] = name

                    self.table[num] = {'value_tuple': value_tuple, 'name': name}

            if 'dest' in instr:
                if old_name:
                    self.env[old_name] = num
                else:
                    self.env[instr['dest']] = num

            new_block.append(instr)
        
        return new_block
    
    @staticmethod
    def sort_set(set):
        """Sort the set of instructions to have constants at the end."""
        out_list = []
        for instr in set:
            if instr[1] == "const":
                out_list.insert(-1, instr)
            else:
                out_list.append(instr)
        return out_list
    
    def pass_block(self, block, inputs):
        if inputs:
            inputs = self.sort_set(inputs)
            for value_tuple in inputs:
                if value_tuple[1] == "const":
                    created_instr = {'op': value_tuple[0], 'dest': value_tuple[1], 'value': value_tuple[2], 'temp': True}
                else:
                    created_instr = {'op': value_tuple[0], 'dest': value_tuple[1], 'args': list(value_tuple[2:]), 'temp': True}
                block.insert(0, created_instr)
        block = self.process_block(block)
        return [instr for instr in block if 'temp' not in instr]

    def run(self, program):
        """Process the entire program."""
        for func in program['functions']:
            new_blocks = []
            for block in BasicBlock.create_blocks_from_function(func['instrs']):
                new_blocks += self.process_block(block)
            func['instrs'] = new_blocks
        return program

def main():
    """Main function to perform local value numbering on input JSON."""
    prog = json.load(sys.stdin)
    lvn_processor = LocalValueNumbering()
    processed_prog = lvn_processor.run(prog)
    json.dump(processed_prog, sys.stdout, indent=2)

if __name__ == "__main__":
    main()
