import ast

class Transform1(ast.NodeTransformer):
    def __init__(self, collector=None, logger=None, module=None, sym_table=None):
        self.sym_table = sym_table
        self.c = collector
        self.logger = logger;
        self.module = module;
    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name):
            try:
                sym = self.sym_table.lookup(node.value.id)
                if sym.is_imported():
                    print('imported symbol %s' % node.value.id)
            except:
                pass
        self.generic_visit(node)
        return node

