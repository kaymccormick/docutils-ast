import sys
import json
import symtable
import ast
from docutils_ast.model import Module
from docutils_ast.visitor.assign import ValueCollector
from docutils_ast.visitor.collect import Collector
from docutils_ast.transform import Transform1

from docutils_ast.logging import StructuredMessage
_ = StructuredMessage
class CodeTranslator:
    def __init__(self, logger):
        self.logger = logger
        with open('files/kinds.json', 'r') as f:
            self.kinds = json.load(fp=f)
        with open('files/namedTypes.json', 'r') as f:
            self.named_types = json.load(fp=f)

    def translate(self, input_filename, output_filename):
        if input_filename is None:
            self.logger.debug(_('Reading from stdin'))
            code = sys.stdin.read()
            file = '-'
        else:
            file = input_filename
            self.logger.debug(_('Reading from %r' % file))
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
    
        collector = Collector(module=the_module, logger=self.logger, sym_table=sym_table)
        collector.visit(tree)
        for import_ in collector.imports:
            self.logger.info(_(None, import_=str(import_)))
        tree = (Transform1(module=the_module, logger=self.logger, sym_table=sym_table, collector=collector)).visit(tree)
    
        analyzer = ValueCollector("main", True, top_level=True, module=the_module, logger=self.logger, sym_table=sym_table, kinds=self.kinds, named_types=self.named_types);
        analyzer.do_visit(tree)
        analyzer.report()
    
        if output_filename:
            f = open(output_filename, 'w')
        else:
            f = sys.stdout
    
        json.dump(analyzer.body, fp=f, indent=4)
        if output_filename:
            f.close()
