import json
import sys
import astor
import ast
import symtable
from docutils_ast.visitor.assign import ValueCollector
import logging
from docutils_ast.model import Module
from docutils_ast.visitor.collect import Collector
from docutils_ast.transform import Transform1, Transform2

def test_assign_1():
    file = 'files/class1.py'
    logger = logging.getLogger('test_assign_1')
    logger.setLevel(logging.DEBUG)
    m = Module()

    v = ValueCollector("test", logger=logger, module=m)
    with open(file, 'r') as f:
        code = f.read()
    sym_table = symtable.symtable(code,file, 'exec')
    tree = ast.parse(code)
    tree = (Transform1(module=m, logger=logger, sym_table=sym_table)).visit(tree)
    code = astor.to_source(tree)

    collector = Collector(module=m, logger=logger, sym_table=sym_table)
    print(tree)
    collector.visit(tree)
    tree = (Transform2(module=m, logger=logger, sym_table=sym_table, collector=collector)).visit(tree)

    analyzer = ValueCollector("main", True, top_level=True, module=m, logger=logger, sym_table=sym_table);
    analyzer.do_visit(tree)
    program = analyzer.output_nodes[-1][0]
    json.dump(program, fp=sys.stderr)
