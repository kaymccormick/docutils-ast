import ast
import sys
import astpretty
import logging
from docutils_ast.model import Import, Module, Class, Function, Method, Variable

from docutils_ast.logging import CustomAdapter, StructuredMessage
_ = StructuredMessage

class Collector(ast.NodeVisitor):
    imports = []
    def __init__(self, module=None, logger=None, sym_table=None):
        self.module = module
        self.logger = logger
        self.sym_tables = [sym_table]
        self.entities = []

    def visit_Module(self,node):
        print(node.__class__.__name__)
        self.entities.append(self.module)
        self.generic_visit(node)
        nodes = []
        for name in self.sym_tables[-1].get_identifiers():
            sym = self.sym_tables[-1].lookup(name)
            if not sym.is_namespace() and sym.is_local():
                variable = Variable(name, self.module, '', sym)
                self.module.add(variable)
                print(sym)                

            
#        self.logger.error(_('', ids=))
        self.entities.pop()

    def visit_ClassDef(self, node):
        print(node.__class__.__name__, node.name)
        (sym,) = filter(lambda x: x.get_name() == node.name, self.sym_tables[-1].get_children())
        self.sym_tables.append(sym)
        class_ = Class(node.name, node, self.module, sym)
        self.entities[-1].add(class_)
        self.entities.append(class_)
        self.generic_visit(node)
        self.entities.pop()
        self.sym_tables.pop()

    def visit_FunctionDef(self, node):
        print(node.__class__.__name__, node.name)
        if len(self.entities) and isinstance(self.entities[-1], Class):
            function = Method(node.name, self.entities[-1])
        else:
            function = Function(node.name, self.entities[-1])
        self.entities[-1].add(function)
        self.entities.append(function)
        sym = None
        try:
            (sym,) = filter(lambda x: x.get_name() == node.name, self.sym_tables[-1].get_children())
        except Exception as ex:
            raise ex
        
        params = ('params',)# *sym.get_parameters())
        locals_ = ('locals', *sym.get_locals())
        globals_ = ('globals', *sym.get_globals())
        frees = ('frees', *sym.get_frees())
        for tuple in (params,locals_,globals_,frees):
            (kind, *rest) = tuple
            for name in rest:
                nsym = sym.lookup(name)
                variable = Variable(name, function, kind, nsym)
                function.add(variable)
                print(kind, nsym.get_name())
        self.sym_tables.append(sym)
        self.generic_visit(node)
        self.entities.pop()        
        self.sym_tables.pop()

    def visit_Import(self, node):
        for name in node.names:
            import_ = Import(name.name, name.asname)
            self.imports.append(import_)
        self.generic_visit(node)

    def default_visit(node):
        print(node)
        super().default_visit(node)
