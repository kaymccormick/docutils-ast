import re
import ast
import sys
import json
import astpretty
from stringcase import camelcase
import logging
import builtins
from docutils_ast.model import Class, ClassProperty, Value, ASTValue
from docutils_ast.logging import CustomAdapter, StructuredMessage
from docutils_ast.util import check_ast, ApplicationError
_ = StructuredMessage
from ast import AST

operators = { 'LtE': '<=',
              'Lt':'<',
              'Gt': '>',
              'Eq':'===',
              'NotEq': '!==',
              'In': 'in',
              'GtE': '>=',
              'NotIn': (1, 'in'),
              'Mod': '%',
              'Add': '+',
              'Sub':'-',
              'Mult': '*',
              'Div': '/',
              'USub': '-',
              'UAdd': '+',
              'Not': '!',
              'BitOr': '|',
              'BitAnd': '&',
}

def node_repr(node):
    r = ast.dump(node)
    if len(r) > 60:
        r = r[0:60] + ' ...'
    return r

def comments_for(node, docstring=None):
    if docstring:
        if '\n' in docstring:
            text = '*\n' + '\n'.join(map(lambda x: ' * ' + x, docstring.split('\n')))
            return [{'type': 'CommentBlock', 'value': text + '\n *'}]
        else:
            return [{'type': 'CommentBlock', 'value': '* ' + docstring + ' *'}]
    return []
    return [{'type': 'CommentBlock', 'value': 'line = %d' % node.lineno }]

class ValueCollector(ast.NodeVisitor):
    in_class_def = False
    enabled = False
    disable_perm = False
    data = None
    context = None
    collected_value = None
    main_node = None
    body = None
    collect_array = None
    collect_scalar = None
    main_collect_array = None
    main_collect_scalar = None
    stack = None
    in_stmt = False
    do_camelcase = False
    collector_level = 0
    cur_node = None
    name = 'root'
    level = 0
    in_nodes = []
    cur_fields = []
    value_index = [-1]
    cur_values = []
    out_values = []
    cur_field = None
    cur_out_nodes = None
    output_nodes = [[]]
    finished_output_nodes = []
    finished_output_statements = []

    def __init__(self, name, enabled=False, do_camelcase=False, module=None, top_level: bool = False, parent: "ValueCollector"=None, graph_file=None, logger=None, sym_table=None, kinds=None, named_types=None):
        if not logger and parent:
            logger_ = parent._logger
        else:
            logger_ = logger
        if not logger:
            logger = logging.getLogger(__name__)
        self._logger = logger_

        self.logger = CustomAdapter(logger_, self)
        self.parent = parent
        self.namespaces = []
        if parent is not None:
            self.major_element = parent.major_element
            self.current_namespace = parent.current_namespace
            self.module = parent.module
            self.graph_file = parent.graph_file
            self.in_nodes[:] = parent.in_nodes[:]
            self.collector_level = parent.collector_level + 1
            self.level = parent.level
            self.sym_table = parent.sym_table
            self.kinds = parent.kinds
            self.named_types = parent.named_types
        else:
            self.major_element = module
            self.current_namespace = module
            self.module = module
            self.graph_file = graph_file
            self.sym_table = sym_table
            self.kinds = kinds
            self.named_types = named_types

        self.top_level= top_level
        self.logger.debug(_('initializing ValueCollector'))
        self.var_scope = { }
        self.stack= []
        self.context = []
        self.data = {}
        self.do_camelcase = do_camelcase
        self.name = name
        self.enabled = enabled

    def generic_visit(self,  node, callSuper=True, newStack=False):
        #self.logger.debug(_('generic_visit(%r, %r, %r)',
        #                  node.__class__.__name__,
        #                  callSuper, newStack)
        self.in_nodes.append(node.__class__)
        if self.enabled:
            if self.main_node is None:
                self.main_node = node
                self.main_collect_array = self.collect_array
                self.main_collect_scalar = self.collect_scalar
        if callSuper:
            self.cur_values.append({})
            for field, value in ast.iter_fields(node):
                self.advance_level(node)
                self.enter_field(node, field)
                self.cur_fields.append(field)
                self.cur_field = field
                if isinstance(value, list):
                    self.cur_values[-1][field] = []
                    self.value_index.append(0)
                    for item in value:
                        if isinstance(item, AST):
                            self.cur_node = None
                            self.visit(item)
                        self.value_index[-1] += 1
                    self.value_index.pop()
                    # it isn't necessarily an output statement, it could be just output nodes!

                    self.cur_values[-1][field] = self.output_nodes[-1]
                    # we haven't set cur_value
                elif isinstance(value, (ast.cmpop, ast.operator, ast.unaryop)):
                    assert value.__class__.__name__ in operators, value.__class__.__name__
                    op = operators[value.__class__.__name__]
                    self.cur_values[-1][field] = op
                elif isinstance(value, ast.expr_context):
                    pass
                elif isinstance(value, AST):
                    self.value_index.append(None)
                    self.visit(value)
                    self.value_index.pop()
                    if len(self.output_nodes[-1]) == 0:
                        raise ApplicationError('empty output nodes', node=value)
                    self.cur_values[-1][field] = self.output_nodes[-1].pop()
                    # we haven't set cur_value
                else:
                    self.cur_values[-1][field] = value
                self.cur_fields.pop()
                self.depart_field(node, field)
                self.retreat_level()
            self.out_values.append(self.cur_values.pop())

        self.in_nodes.pop()
        if self.main_node == node:
            # obtain collected output node(s)
            # how do we know if we've any output?
            try:
                self.collected_value = self.collected_output_nodes()
            except IndexError:
                self.logger.error(_('unable to retrieve collected output nodes', output_nodes=self.output_nodes))

    def visit(self, node):
        try:
            super().visit(node)
        except Exception as ex:
            raise ex
            self.logger.error(_(str(ex), type=ex.__class__.__name__, pretty=astpretty.pformat(node)))
            exit(1)

    def visit_Module(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        expr = { 'type': 'File', 'program': {
            'type': 'Program', 'body': value['body'] } }
        self.collect_output_node(expr)

    def visit_Import(self, node):
        self.generic_visit(node)
        values = self.cur_values[-1]

    def visit_Index(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        self.collect_output_node(value['value'])
        self.logger.info(_('value', value=value))
    def visit_Lambda(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        #self.collect_output_node(value['value'])
        self.logger.info(_('value', value=value))
        if isinstance(value['body'], dict):
            body = value['body'];
        else:
            body = {'type': 'BlockStatement', 'body': value['body']}

        expr = { 'type': 'ArrowFunctionExpression', 'params': value['args'],
                     'body': body }
        self.collect_output_node(expr)
    def visit_Yield(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        expr= { 'type': 'YieldExpression', 'argument': value['value'] }
        self.collect_output_node(expr)
        self.logger.info(_('value', value=value))

    def visit_IfExp(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        #self.collect_output_node(value['value'])
        expr = { 'type':'ConditionalExpression', 'test': value['test'],
                 'consequent': value['body'],
                 'alternate': value['orelse']}
        self.collect_output_node(expr)

    def visit_Slice(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        self.collect_output_literal(value)

    def visit_Not(self, node):
        self.generic_visit(node, False)
        self.collect_output_literal('!')
        
    def visit_Assign(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
#        self.logger.info(_('value', value=value))
        targets = value['targets']
        assign_value = value['value']
        target_nodes = []
        var_decls = []
        output_stmts = []
        while targets:
            target = targets.pop()
            self.logger.debug(_('target of assignment', node=target))
            (new_var, class_prop, node) = self.process_target(target, assign_value)
            if new_var and node:
                var_decls.append(node)
            elif not class_prop and node:
                target_nodes.append(node)

        if issubclass(self.in_nodes[-1], ast.ClassDef):
            pass
        else:
            if len(var_decls) > 1:
                tmp_var_name = '_tmp1';
                tmp_var = { 'type': 'Identifier', 'name': tmp_var_name }
                output_stmts.append({'type': 'VariableDeclaration',
                                  'declarations': [
                                      {'type': 'VariableDeclarator',
                                       'id': tmp_var, 'init': right }],
                                  'kind': 'const'})
                for var_decl in var_decls:
                    var_decl['declarations'][0]['init'] = tmp_var
                    output_stmts.append(var_decl)
            else:
                first = True
                var_decl = None
                if len(var_decls) == 1:
                    var_decl = var_decls[0]

                right = assign_value
                while len(target_nodes):
                    left = target_nodes.pop()
                    if var_decl is not None:
                        var_decl['declarations'][0]['init'] = right
   
                    right = { 'type': 'AssignmentExpression',
                              'operator': '=',
                              'left': left,
                              'right': right
                              }
                if var_decl is not None:
                    var_decl['declarations'][0]['init'] = right
                    stmt = var_decl
                else:
                    stmt = { 'type': 'ExpressionStatement', 'expression': right }
                output_stmts.append(stmt)
                # self.disable_perm = True
        for stmt in output_stmts:
            self.collect_output_statement(stmt)
            
        self.logger.debug(_('output statements: %r'% output_stmts))
 
    def process_target(self, target, value):
        annotation = None
        new_var = False
        if target['type'] == 'Identifier':
            n = target['name']
            if issubclass(self.in_nodes[-1], ast.ClassDef):
                # assignment is in class body, create property
                self.logger.debug(_('in class, create property'))
                prop = ClassProperty(self.major_element, n, ASTValue(value))
                self.logger.debug(_('adding class property %s' % n))
                self.major_element.add(prop)
                self.current_namespace.store_name(n, prop)
                return (False, True, None)
            else:
                var = self.find_var(target)
                if var is None:
                    new_var = True
                    self.register_var(target)
                    if annotation is not None:
                        target['typeAnnotation'] = annotation;
                    result = { 'type': 'VariableDeclaration', 'declarations': [{'type': 'VariableDeclarator', 'id': target }], 'kind': 'let' }
                    return (True, False, result)
                if not new_var:
                    return (False, False, target)
        else:
            return (False, False, target)

    def visit_Tuple(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        elts = value['elts']
        expr = { "type": 'CallExpression',
                 'callee': { 'type': 'Identifier', 'name': 'Tuple'},
                 'arguments': elts,
                 'comments': comments_for(node) }
        self.collect_output_node(expr)
        
    def visit_List(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        expr = { "type": 'ArrayExpression', 'elements': value['elts'], 'comments': comments_for(node) } # fixme
        self.collect_output_node(expr)

    def visit_Num(self,node):
        if not self.enabled:
            self.generic_visit(node)
            return
        self.collect_output_node({ 'type': 'Literal', 'value': node.n });
        self.generic_visit(node, False)

    def visit_Str(self,node):
        if not self.enabled:
            self.generic_visit(node)
            return
        self.collect_output_node({ 'type': 'StringLiteral', 'value': node.s });
        self.generic_visit(node, False)

    def visit_Name(self, node):
        if node.id == 'self':
            expr= { 'type': 'ThisExpression' }
        else:
            name = node.id
            expr= { 'type': 'Identifier', 'name': camelcase(node.id) if self.do_camelcase and not re.match('__', node.id) else node.id }
            var = self.find_var(expr)
            if var is None:
                self.logger.debug(_('Registering variable for', node=expr))
                self.register_var(expr)
        self.collect_output_node(expr)
        self.generic_visit(node, False)

    def visit_Attribute(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        expr = {'type':'MemberExpression','object':value['value'],
                'property': { 'type': 'Identifier', 'name': value['attr']} }
        self.logger.info(_('expression', expr=expr))
        self.collect_output_node(expr)
    
    def oldvisit_Attribute(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return

        v = ValueCollector('attribute.value', True, parent=self)
        v.do_visit(node.value)
        object = v.finished_output_nodes[-1].pop()
        id_name = camelcase(node.attr) if self.do_camelcase and not re.match('__', node.attr) else node.attr
        if object['type'] == 'ThisExpression':
            # do we endure we are 'in' a class?
            assert isinstance(self.major_element, Class), 'major element should be class'
            if not self.current_namespace.name_exists(id_name):
                prop = ClassProperty(self.major_element, id_name)
                self.major_element.add(prop)
                self.current_namespace.store_name(id_name, prop)

        expr = { 'type': 'MemberExpression',
                 'object': object,
                 'property': { 'type': 'Identifier', 'name': id_name },
                 'comments': comments_for(node) }
        self.collect_output_node(expr)
        self.generic_visit(node, False)

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        #self.collect_output_node(value['value'])
        expr = {'type': 'UnaryExpression', 'operator': value['op'], 'argument': value['operand'],
                'prefix': True}
        self.collect_output_node(expr)

    def oldvisit_UnaryOp(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return
        operator = None
        if isinstance(node.op, ast.Not):
            operator = '!'
        elif isinstance(node.op, ast.USub):
            operator = '-'
        else:
            self.logger.error(_('%s' % astpretty.pformat(node.value)))
            exit(5)

        self.generic_visit(node)
        # now we need to find the output from our descent
        expr = { 'type': 'UnaryExpression', 'operator': operator, 'argument': self.finished_output_nodes[-1].pop(), 'prefix': True }
        self.collect_output_node(expr)

    def visit_If(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
#        self.logger.info(_('value', value=value))
        expr = { 'type': 'IfStatement', 'test': value['test'], 'consequent': { 'type': 'BlockStatement', 'body': value['body'] } }
        if 'orelse' in value and len(value['orelse']):
            expr['alternate'] = { 'type': 'BlockStatement', 'body': value['orelse'] }
        self.collect_output_node(expr)
        
        
    def oldvisit_If(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return
        v = ValueCollector('', True, parent=self)
        v.do_visit(node.test)
        test = v.finished_output_nodes[-1].pop()

        body= []
        for stmt in node.body:
            v2 = ValueCollector('', True, parent=self)

            v2.do_visit(stmt)
            body.extend(v2.body)

        orelse= []
        for stmt in node.orelse:
            v3 = ValueCollector('', True, parent=self)
            v3.do_visit(stmt)
            orelse.extend(v3.body)

        expr = { 'type': 'IfStatement', 'test': test, 'consequent':{ 'type': 'BlockStatement', 'body': body } }
        if len(orelse):
            expr['alternate'] = { 'type': 'BlockStatement', 'body': orelse }
        self.cur_node = expr
        self.collect_output_statement(expr)

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        #self.collect_output_node(value['value'])
        self.logger.info(_('value', value=value))
        values = value['values']
        left = values.pop(0)
        while len(values):
            left = { 'type': 'LogicalExpression', 'operator': value['op'], 'left': left, 'right': values.pop(0) }
        self.collect_output_node(left)

    def visit_BinOp(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
#        self.logger.info(_('value', value=value))
        expr = { 'type': 'BinaryExpression', 'operator': value['op'], 'left': value['left'], 'right': value['right'], 'comments': comments_for(node) }
        self.collect_output_node(expr)

    def oldvisit_BinOp(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return
        v = ValueCollector("left binop", True, parent=self)
        v.do_visit(node.left)
        left = v.finished_output_nodes[-1].pop()
        v2 = ValueCollector("right binop", True, parent=self)
        v2.do_visit(node.right)
        right = v2.finished_output_nodes[-1].pop()

        operator = None
        if isinstance(node.op, ast.Add):
            operator = '+'
        if isinstance(node.op, ast.Sub):
            operator = '-'
        if isinstance(node.op, ast.Mult):
            operator = '*'
        if operator is not None:
            expr = { 'type': 'BinaryExpression', 'operator': operator, 'left': left, 'right': right, 'comments': comments_for(node) }
        else:
            expr = { 'type':'CallExpression', 'callee': { 'type':'Identifier', 'name': 'pyBinOp'}, 'arguments': [{ 'type': 'StringLiteral', 'value': node.op.__class__.__name__}, left, right], 'comments': comments_for(node)}
        self.collect_output_node(expr)
        self.generic_visit(node, False)

    def visit_NameConstant(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return
        expr = None
        if node.value is None:
            expr = { 'type': 'Identifier', 'name': 'undefined' }
        if node.value in (True, False):
            expr = { 'type': 'Literal', 'value': node.value }
        if expr is not None:
            self.cur_node = expr
            self.collect_output_node(expr)

        self.generic_visit(node, False)

    def visit_Dict(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        self.logger.info(_('value', value=value))
        keys =value['keys']
        values = value['values']
        props = []
        for i in range(0, len(keys)):
            props.append({'type': 'Property', 'key': keys[i], 'value': values[i] })

        expr = { 'type': 'ObjectExpression', 'properties': props, 'comments': comments_for(node) }
        self.collect_output_node(expr)

    def visit_Call(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        self.logger.info(_('value', value=value))
        
        expr = {'type': 'CallExpression',
                      'callee': value['func'],
                      'arguments': value['args'],
                      'comments': comments_for(node)
             }
        self.collect_output_node(expr)
        return
        # func_c = ValueCollector('func', True, parent=self, do_camelcase=False)
        # func_c.do_visit(node.func)
        # func = func_c.finished_output_nodes[-1].pop()
        # args = []
        # for arg in node.args:
        #     arg_c = ValueCollector('arg', True, parent=self)
        #     arg_c.do_visit(arg)
        #     value = arg_c.finished_output_nodes[-1].pop()
        #     args.append(value)
        # expr = None
        # try:
        #     if func['type'] == 'Identifier':
        #         funcName = func['name']
        #         if builtins.__dict__[funcName]:
        #             self.logger.debug(_('found builtin %s' % funcName))
        #         if funcName == "Exception":
        #             expr = { 'type': 'NewExpression',
        #                      'callee': func,
        #                      'arguments': args }
        #         elif funcName == "isinstance":
        #             # hande right hand side tuple
        #             expr = { 'type': 'BinaryExpression',
        #                      'operator': 'instanceoof',
        #                      'left': args[0],
        #                      'right': args[1] }
        #         elif funcName == "len":
        #             assert len(args) == 1, 'length of args should be 1'
        #             expr = { 'type': 'MemberExpression',
        #                      'object': args[0],
        #                      'property': {'type':'Identifier', 'name':'length'},
        #             }
        #         else:
        #             args.insert(0, {'type':'StringLiteral', 'value': funcName })
        #             expr = { 'type': 'CallExpression',
        #                      'callee': {'type': 'Identifier', 'name': '_pyBuiltin'},
        #                      'arguments': args }
        # except KeyError:
        #     pass
        #
        # if expr is None:
        #     expr = { 'type': 'CallExpression',
        #              'callee': func,
        #              'arguments': args,
        #              'comments': comments_for(node)
        #     }
        # self.collect_scalar = True
        # assert expr
        # self.cur_node = expr
        # self.collect_output_node(expr)
        # self.generic_visit(node)

    def visit_Starred(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        expr = { 'type': 'SpreadElement', 'argument': value['value'], 'comments': comments_for(node) }
        self.collect_output_node(expr)
        self.logger.info(_('value', value=value))

    def visit_Subscript(self, node):
        self.generic_visit(node, True)
        value = self.out_values.pop()
        self.logger.info(_('value', value=value))
        if 'slice' in value:
            slice = value['slice']
            if 'lower' in slice:
                expr = { 'type':'CallExpression', 'callee': { 'type': 'MemberExpression', 'object': value['value'], 'property': { 'type':'Identifier', 'name': 'slice' } }, 'arguments': [value['slice']['lower'] or { 'type': 'Identifier', 'name': 'undefined' }, value['slice']['upper']], 'comments': comments_for(node) }
            else:
                expr = { 'type': 'MemberExpression', 'object': value['value'], 'property': value['slice']}
            self.logger.info(_('expr', expr=expr))
        else:
            raise Error('')
        if not expr:
            raise Error('no node')
        self.collect_output_node(expr)

    def visit_ListComp(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return
        self.collect_scalar = True
        expr = { 'type': 'TSUndefinedKeyword', 'comments': comments_for(node) }
        self.collect_output_node(expr)
        self.generic_visit(node, False)
    def visit_GeneratorExp(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return
        self.collect_scalar = True
        expr = { 'type': 'TSUndefinedKeyword' }
        self.cur_node = expr
        self.collect_output_node(expr)
        self.generic_visit(node, False)
    def visit_Compare(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        left = value['left']
        ops = value['ops']
        comparators = value['comparators']
        while ops:
            op = ops.pop()
            comparator = comparators.pop()
            left = { 'type': 'BinaryExpression',
                     'left': left,
                     'operator':op,
                     'right': comparator }
        expr = left
        self.collect_output_node(expr)
        
    def oldvisit_Compare(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return
        if len(node.ops) != 1:
            expr = { 'type': 'TSUndefinedKeyword' }
            self.cur_node = expr
            self.collect_output_node(expr)
            self.collect_scalar = True
            self.generic_visit(node)
            return

        assert len(node.ops) == 1, 'node ops 1'
        # fix me!
        op = node.ops[0]
        operator = None
        negate = False
        if isinstance(op, (ast.Eq, ast.Is)):
            operator = '==='
        elif isinstance(op, (ast.NotEq, ast.IsNot)):
            operator = '!=='
        elif isinstance(op, (ast.In)):
            operator = 'in'
        elif isinstance(op, (ast.Gt)):
            operator = '>'
        elif isinstance(op, (ast.Lt)):
            operator = '<'
        elif isinstance(op, (ast.LtE)):
            operator = '<='
        elif isinstance(op, (ast.GtE)):
            operator = '>='
        elif isinstance(op, (ast.NotEq)):
            operator = '!=='
        elif isinstance(op, (ast.NotIn)):
            negate = True
            operator = 'in'
        else:
            print(astpretty.pformat(node))
            exit(2)

        comparator = node.comparators[0]
        v = ValueCollector("compator", True, parent=self)
        v.do_visit(comparator)
        comparator = v.finished_output_nodes[-1].pop()

        v2 = ValueCollector("left", True, parent=self)
        v2.do_visit(node.left)
        left = v2.finished_output_nodes[-1].pop()

        expr = { 'type': 'BinaryExpression', 'operator': operator, 'left': left, 'right': comparator, 'comments': comments_for(node) }
        if negate:
            expr = { 'type': 'UnaryExpression', 'operator': '!', 'prefix': True, 'operand': expr }
        self.cur_node = expr
        self.collect_output_node(expr)
        self.collect_scalar = True
        self.generic_visit(node, False)

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        expr = { 'type': 'FunctionDeclaration', 'params': value['args'],
                 'id':{ 'type':'Identifier', 'name': value['name']},
                 'body':{ 'type':'BlockStatement', 'body': value['body'] } }
        if self.in_class_def:
            expr['params'] = expr['params'][1:]
            expr['type'] = 'TSDeclareMethod'
            expr['access'] = 'public'
            if node.name == "__init__":
                expr['kind'] = 'constructor'
                expr['key'] = { 'type': 'Identifier', 'name': 'constructor' }

            else:
                expr['kind'] ='method'
                expr['key'] = { 'type': 'Identifier', 'name': node.name }
        else:
            expr['name'] = node.name
        
        self.collect_output_node(expr)

    def visit_arguments(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        self.collect_output_literal(value['args'])

    def oldvisit_FunctionDef(self, node):
        assert isinstance(node.args, ast.arguments), 'args'
        if re.match('__', node.name):
            return
        args = []
        i = 0
        for arg in node.args.args:
            v = ValueCollector('functionDef(%s, arg[%d])' % (node.name, i),
                               True, parent=self)
            i += 1
            v.do_visit(arg)
            args.append(v.finished_output_nodes[-1].pop())

        oldEnabled = self.enabled
        self.enabled = True
        self.generic_visit(node, True, True)
        self.enabled = oldEnabled


        expr = { 'type': 'FunctionDeclaration', 'params': args,
                 'id': { 'type': 'Identifier', 'name': node.name} ,
                 'body': { 'type': 'BlockStatement', 'body': self.result} }
        if self.in_class_def:
            raise Exception('')
            expr['params'] = args[1:]
            expr['type'] = 'TSDeclareMethod'
            expr['access'] = 'public'
            if node.name == "__init__":
                expr['kind'] = 'constructor'
                expr['key'] = { 'type': 'Identifier', 'name': 'constructor' }

            else:
                expr['kind'] ='method'
                expr['key'] = { 'type': 'Identifier', 'name': node.name }
        else:
            expr['name'] = node.name

        self.cur_node = expr
        self.collect_output_statement(expr)

    def visit_arg(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        #self.collect_output_node(value['value'])
        self.logger.info(_('value', node=ast.dump(node), value=value))
        arg = value['arg']
            
        expr = { 'type': 'Identifier',
                 'name': arg,
                 'comments': comments_for(node) }
        self.collect_output_node(expr)

    def visit_ClassDef(self, node):
        name = node.name
        self.in_class_def = True
        assert not self.current_namespace.name_exists(name), 'name %s exists in scope' % name
        class_ = Class(name, node=None)
        self.current_namespace.store_name(name, class_)
        self.major_element = class_
        self.namespaces.append(self.current_namespace)
        self.current_namespace = class_
        self.generic_visit(node)
        self.current_namespace = self.namespaces.pop()
        self.in_class_def = False
        value = self.out_values.pop()

#        self.logger.info(_('value', value=value))

        assert not self.in_class_def


        body = value['body']
        for elem in class_.elems:
            body.insert(0, elem.ast_node())

        expr = { 'type': 'ClassDeclaration',
                 'id': { 'type': 'Identifier', 'name': name },
                 'body':  { 'type': 'ClassBody', 'body': body,
                 }}
        if len(value['bases']):
            expr['superClass'] = value['bases'][0]

        self.collect_output_literal(expr)
    
    def oldvisit_ClassDef(self, node):
        try:
            oldEnabled = self.enabled
            assert not self.in_class_def
            self.in_class_def = True
            self.enabled = True

            expr = { 'type': 'ClassDeclaration',
                     'id': { 'type': 'Identifier', 'name': node.name }}

            assert not self.current_namespace.name_exists(node.name), 'name %s exists in scope' % node.name
            class_ = Class(node.name, node=expr)
            self.current_namespace.store_name(node.name, class_)
            self.major_element = class_
            self.namespaces.append(self.current_namespace)
            self.current_namespace = class_
            # collect the body
            self.cur_node = expr
            self.generic_visit(node, True, True)
            self.current_namespace = self.namespaces.pop()
            self.enabled = oldEnabled

            body = self.result
            for elem in class_.elems:
                body.insert(0, elem.ast_node())

            expr['body'] = { 'type': 'ClassBody', 'body': body }
            if len(node.bases):
                base = node.bases[0]
                v = ValueCollector('', True, do_camelcase=False, parent=self)
                v.do_visit(base)
                b = v.finished_output_nodes[-1].pop()
                expr['superClass'] = b

            self.in_class_def = False
            self.collect_output_statement(expr)
        except Exception as ex:
            self.logger.error(_('major element is %r' % self.major_element))
            raise ex
            exit(23)

    def visit_Expr(self, node):
        oldEnabled = self.enabled
        self.enabled = True
        self.generic_visit(node, True)
        value = self.out_values.pop()
        the_expr = value['value']
        expr = { 'type': 'ExpressionStatement',
                 'expression': the_expr  }
        if the_expr['type'] == 'StringLiteral':
            ## standalone doc string
            comments = comments_for(node, the_expr['value'])
#            if not len(self.cur_values[-1][field]):
#                expr = { 'type': 'EmptyStatement', 'comments': comments }
#            else:
#                self.body[-1]['comments'].extend(comments)
 #               expr = { 'type': 'EmptyStatement' }

        self.collect_output_statement(expr)
        self.enabled = oldEnabled

    def visit_Return(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        if 'value' in value and value['value']:
            expr = { 'type': 'ReturnStatement', 'argument': value['value'] }
        else:
            expr = { 'type': 'ReturnStatement', 'argument':None }
        self.collect_output_statement(expr)
        
    def oldvisit_Return(self, node):
        try:
            oldEnabled = self.enabled
            self.enabled = True
            len1 = len(self.out_values)
            self.generic_visit(node, True)
            expr = { 'type': 'ReturnStatement' }
            if len(self.out_values) > len1:
                expr['argument'] = self.out_values.pop()
            self.collect_output_statement(expr)
            self.enabled = oldEnabled
        except Exception as ex:
            raise ex
            self.logger.error(_('major element is %r' % self.major_element))
            self.logger.error(_(ex))
            self.logger.error(_(astpretty.pformat(node)))
            exit(21)

    def find_var(self, node):
        assert node['type'] == 'Identifier'
        if node['name'] in self.var_scope:
            return self.var_scope[node['name']]
        return None

    def register_var(self, node):
        assert node['type'] == 'Identifier'
        assert node['name'] not in self.var_scope
        self.var_scope[node['name']] = node

    def collect_node(self, name, node, **kwargs):
        kwargs['parent'] = self
        my_vc = ValueCollector('%s.%s' % (self.name, name), True, **kwargs)
        my_vc.do_visit(node)
        # output depends on what was visited
        # result is the 'body' output ?
        return my_vc

    def report(self):
        pass

    def visit_Raise(self, node):
        self.generic_visit(node)
        value = self.out_values[-1]
        exc = value['exc']
        if exc:
            expr = { 'type': 'ThrowStatement',  'argument': value['exc'] }
        else:
            expr = { 'type': 'ThrowStatement' }
        self.collect_output_statement(expr)

    def visit_For(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        expr = {'type':'ForOfStatement', 'left': value['target'],
                'right':value['iter'],
                'body': { 'type':'BlockStatement', 'body': value['body']}}
        self.collect_output_statement(expr)
#        self.collect_output_node(value['value'])
#        self.logger.info(_('value', value=value))
#        exit(1)

    def visit_Try(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        self.logger.info(_('value', value=value))
        expr = { 'type': 'TryStatement', 'block': { 'type':'BlockStatement', 'body': value['body']}}
        self.collect_output_statement(expr)

    def visit_ExceptHandler(self, node):
        self.generic_visit(node)
        value = self.out_values.pop()
        expr = { 'type':'CatchClause', 'param': { 'type':'Identifier','name': value['name'] }, 'body': { 'type': 'BlockStatement', 'body': value['body'] }}
        self.collect_output_node(expr)


#    def visit_Eq(self, node):
#        self.collect_output_literal('===')
#    def visit_Lt(self, node):
#        self.collect_output_literal('<')
#    def visit_LtE(self, node):
#        self.collect_output_literal('<=')
#    def visit_Gt(self, node):
#        self.collect_output_literal('>')
#    def visit_GtE(self, node):
#        self.collect_output_literal('>=')
#    def visit_Mod(self, node):
#        self.collect_output_literal('%')
#    def visit_And(self, node):
#        self.collect_output_literal('&&')
#    def visit_Or(self, node):
#        self.collect_output_literal('||')
#    def visit_Add(self, node):
#        self.collect_output_literal('+')
#    def visit_Sub(self, node):
#        self.collect_output_literal('-')
#    def visit_USub(self, node):
#        self.collect_output_literal('-')
#    def visit_BitOr(self, node):
#        self.collect_output_literal('|')
#
    def do_visit(self, node, *args, **kwargs):
        self.logger.debug(_('do_visit(%s)' % node_repr(node)))
        r = self.visit(node, *args, **kwargs)

    def __repr__(self):
        return '%s<%r>' % (self.__class__.__name__, self.collected_value)

    def advance_level(self, node):
#        self.logger.debug(_('Advance level.', cur_level=self.level, new_level=self.level + 1))
        self.output_nodes.append([])
        self.finished_output_statements.append([])
        self.level += 1

    def retreat_level(self):
#        self.logger.debug(_('Retreat level.', cur_level=self.level, new_level=self.level - 1))
        self.finished_output_nodes.append(self.output_nodes.pop())
        self.finished_output_statements.pop()
        self.level -= 1

    def collect_output_literal(self, literal):
        self.output_nodes[-1].append(literal)
    def collect_output_node(self, output_node):
        # do something useful with this.
        correct = None
        try:
            correct = check_ast(output_node)
        except Exception as ex:
            self.logger.error(_(ex.message))

        self.output_nodes[-1].append(output_node)
    def collected_output_nodes(self):
        return self.finished_output_nodes[-1]

    def collect_output_statement(self, stmt):
        if 'comments' not in stmt:
            stmt['comments'] = []
        self.collect_output_node(stmt)
        return

        if not check_ast(stmt):
            self.logger.error(_('AST node is invalid', in_nodes=self.in_nodes, astnode=stmt))
            raise ApplicationError('Invalid ast node',node=stmt);
        self.finished_output_statements[-1].append(stmt)

    def enter_field(self,node, field):
        pass
    def depart_field(self,node, field):
        pass
