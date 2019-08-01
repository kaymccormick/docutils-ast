import ast

from docutils import nodes

types_of_interest = (nodes.NodeVisitor,)

class ClassVisitor(ast.NodeVisitor):
    def __init__(self):
        pass

    # a class can extend a variable or an 'attribute' - what's the difference?
    # we are looking for rel. basic invocations. Python can also have many
    # bases. we only care to examne one.
    def visit_ClassDef(self, node):
        bases = []
        for base in node.bases:
            # how would we match on what we want??
            if isinstance(base, ast.Attribute):
                name = base.attr
            else:
                name = base.id
            self.stats['bases'].setdefault(name, 0);
            self.stats['bases'][name] += 1
            self.stats['nonLeafClasses'].setdefault(name, 1)
            if name in impBases:
                self.stats['subTypes'][name].append(node.name)
            bases.append(name);
                
        self.stats["class"].append({ 'name': node.name, 'bases': bases })
        self.inClass = node.name
        self.generic_visit(node)
        
