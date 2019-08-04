import ast
import sys
import astpretty
import logging
from docutils_ast.model.py import Import

from docutils_ast.logging import CustomAdapter, StructuredMessage
_ = StructuredMessage

class Collector(ast.NodeVisitor):
    imports = []
    def __init__(self, module=None, logger=None, sym_table=None):
        self.module = module
        self.logger = logger
        self.sym_table = sym_table

    def visit_Import(self, node):
        for name in node.names:
            import_ = Import(name.name, name.asname)
            self.imports.append(import_)
