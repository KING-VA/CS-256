# Redo SSA so that it takes in bril and passes out bril in SSA form -- no CFG conversion gimmicks anymore
import json
import sys
import click

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
    
    
    
@click.command()
@click.option('debug', '--debug', is_flag=True, default=False, help='Enable debugging')
@click.option('to_ssa', '--to-ssa', is_flag=True, default=False, help='Convert to SSA')
@click.option('from_ssa', '--from-ssa', is_flag=True, default=False, help='Convert from SSA')
@click.option('round_trip', '--round-trip', is_flag=True, default=False, help='Round trip conversion')
@click.option('check_ssa', '--check-ssa', is_flag=True, default=False, help='Check if in SSA form')
def main(debug, to_ssa, from_ssa, round_trip, check_ssa):
    bril = json.load(sys.stdin)
    if check_ssa:
        print(json.dumps(SSA.check_ssa(bril, debug=debug)))
    elif to_ssa:
        pass
    elif from_ssa:
        pass
    elif round_trip:
        pass

if __name__ == '__main__':
    main()