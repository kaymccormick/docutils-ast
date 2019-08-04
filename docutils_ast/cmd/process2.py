import sys
import symtable
import json
import re
import ast
from pprint import pprint
from sys import stderr
import logging
import astpretty
from docutils_ast.visitor.assign import ValueCollector
from docutils_ast.visitor.collect import Collector
from docutils_ast.transform import Transform1
from docutils_ast.model import Module
from docutils_ast.logging import StructuredMessage
_ = StructuredMessage
import docutils_ast.model
import argparse
import logging.config

docutils_dir = '/local/home/jade/JsDev/docutils-monorepo/docutils-ast/venv/lib/python3.7/site-packages/docutils/'

def main(argv, logger_name="process2.py"):
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input-filename')
    parser.add_argument('-o', '--output-filename')
    args = parser.parse_args(argv)
    if args.input_filename:
        file = args.input_filename

    db_credentials = { "database":"logs","host":"localhost","user":"logs","password":"poopfact"}
    
    try:
        logging.config.fileConfig('logging.conf')
    except Exception as ex:
        print(e.message, fp=sys.stderr)
        exit(1)
        pass

    with open('kinds.json', 'r') as f:
        kinds = json.load(fp=f)
    with open('namedTypes.json', 'r') as f:
        named_types = json.load(fp=f)
    
    MAXDEBUG = 10
    debug = MAXDEBUG
    graph_out = open('graph.txt', 'w')
    
    logger = logging.getLogger(logger_name)
    if file is None:
        logger.debug(_('Reading from stdin'))
        code = sys.stdin.read()
        file = '-'
    else:
        logger.debug(_('Reading from %r' % file))
        with open(file, 'r') as source:
            code = source.read()

    sym_table = symtable.symtable(code,file, 'exec')
    tree = ast.parse(code)

    the_module = Module(file=file)
    cur = sym_table
    sym_tables = {}
    def proc_sym_table(st):
        id_ = st.get_id()
        assert id_ not in sym_tables
        o = { 'id': id_, 'symbols': {}, 'children': [] }
        for child in st.get_children():
            o['children'].append(proc_sym_table(child))
        for sym in st.get_symbols():
            t = {'name':sym.get_name(), 'is_imported': sym.is_imported(), 'is_local': sym.is_local(), 'is_assigned': sym.is_assigned(), 'namespaces': []}
            for namespace in sym.get_namespaces():
                t['namespaces'].append(namespace.get_id())
            if not len(t['namespaces']):
                del t['namespaces']
            assert not sym.get_name() in o['symbols']
            o['symbols'][sym.get_name()] = t;
        return o
            
    out = proc_sym_table(cur)

    collector = Collector(module=the_module, logger=logger, sym_table=sym_table)
    collector.visit(tree)
    for import_ in collector.imports:
        logger.info(_(None, import_=str(import_)))
    tree = (Transform1(module=the_module, logger=logger, sym_table=sym_table, collector=collector)).visit(tree)

    analyzer = ValueCollector("main", True, top_level=True, module=the_module, graph_file=graph_out, logger=logger, sym_table=sym_table, kinds=kinds, named_types=named_types);
    analyzer.do_visit(tree)
    analyzer.report()

    if args.output_filename:
        f = open(args.output_filename, 'w')
    else:
        f = sys.stdout

    json.dump(analyzer.body, fp=f, indent=4)
    if args.output_filename:
        f.close()
#    with open('out.json', 'w') as fp:
#        json.dump(analyzer.body, fp=fp, indent=4)

#    with open('out.json', 'w') as outf:
#        json.dump(analyzer.stats['elements'], fp=outf)
    
if __name__ == '__main__':
    print(dir())
    main(sys.argv[1:], logger_name='process2')
