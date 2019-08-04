import sys
import json
import re
import ast
from pprint import pprint
from sys import stderr
import logging
import astpretty
from docutils_ast.visitor.assign import ValueCollector
from docutils_ast.model import Module
from docutils_ast.logging import StructuredMessage
_ = StructuredMessage
import docutils_ast.model

import logging.config

def main(file=None, logger_name="process2.py"):
    db_credentials = { "database":"logs","host":"localhost","user":"logs","password":"poopfact"}
    
    try:
        logging.config.fileConfig('logging.conf')
    except Exception as ex:
        print(e.message, fp=sys.stderr)
        exit(1)
        pass

    MAXDEBUG = 10
    debug = MAXDEBUG
    graph_out = open('graph.txt', 'w')
    
    docutils_dir = '/local/home/jade/JsDev/docutils-monorepo/docutils-ast/venv/lib/python3.7/site-packages/docutils/'
    #    file = docutils_dir + '/parsers/rst/states.py'
    #    file = sys.argv[1]

    logger = logging.getLogger(logger_name)
    if file is None:
        logger.debug(_('Reading from stdin'))
        tree = ast.parse(sys.stdin.read())
    else:
        logger.debug(_('Reading from %r' % file))
        with open(file, 'r') as source:
            tree = ast.parse(source.read());

    the_module = Module(file=file)
    analyzer = ValueCollector("main", True, top_level=True, module=the_module, graph_file=graph_out, logger=logger);
    analyzer.do_visit(tree)
    analyzer.report()
    json.dump(analyzer.body, fp=sys.stdout, indent=4)
#    with open('out.json', 'w') as fp:
#        json.dump(analyzer.body, fp=fp, indent=4)

#    with open('out.json', 'w') as outf:
#        json.dump(analyzer.stats['elements'], fp=outf)
    
if __name__ == '__main__':
    print(dir())
    main(*sys.argv[1:], logger_name='process2')
