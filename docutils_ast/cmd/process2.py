import sys
import json
import re
import ast
from pprint import pprint
from sys import stderr
import logging
import astpretty
from docutils_ast.visitor.assign import ValueCollector

import logging.config

def main(file):
    try:
        logging.config.fileConfig('logging.conf')
    except:
        pass

    MAXDEBUG = 10
    debug = MAXDEBUG
    mainout = open('out.txt', 'w')
    
    docutils_dir = '/local/home/jade/JsDev/docutils-monorepo/docutils-ast/venv/lib/python3.7/site-packages/docutils/'
    file = docutils_dir + '/parsers/rst/states.py'
    file = sys.argv[1]
    
    with open(file, 'r') as source:
        tree = ast.parse(source.read());
    
    analyzer = ValueCollector("main");
    analyzer.visit(tree)
    analyzer.report()
    json.dump(analyzer.body, fp=sys.stdout, indent=4)
#    with open('out.json', 'w') as fp:
#        json.dump(analyzer.body, fp=fp, indent=4)

#    with open('out.json', 'w') as outf:
#        json.dump(analyzer.stats['elements'], fp=outf)
    
if __name__ == '__main__':
    main(*sys.argv[1:])
