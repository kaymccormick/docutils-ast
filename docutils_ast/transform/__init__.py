
import ast

class Transform1(ast.NodeTransformer):
    def __init__(self, logger=None, module=None, sym_table=None):
        self.sym_table = sym_table
        self.logger = logger;
        self.module = module;
    def visit_If(self, node):
        self.generic_visit(node)
        if isinstance(node.test, ast.Compare):
            if isinstance(node.test.left, ast.Attribute):
                if isinstance(node.test.left.value, ast.Name) and node.test.left.attr == 'version_info':
                    if node.test.left.value.id == 'sys':
                        if isinstance(node.test.comparators[0], ast.Tuple):
                            if len(node.test.comparators[0].elts) == 1 and isinstance(node.test.comparators[0].elts[0], ast.Num) and node.test.comparators[0].elts[0].n == 3:
                                if isinstance(node.test.ops[0], ast.Lt):
                                    return node.orelse;
                                else:
                                    return node.body;
        return node
    def visit_Name(self, node):
        self.generic_visit(node)
        if node.id in ('arguments','new', 'function', 'default'):
            node.id = '___' + node.id;
        return node


class Transform2(ast.NodeTransformer):
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
