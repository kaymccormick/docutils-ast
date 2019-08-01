import ast
import sys
from docutils import nodes
import json
from stringcase import camelcase

class NodeFinder(ast.NodeVisitor):
    def generic_visit(self,  node):
        pass
    
