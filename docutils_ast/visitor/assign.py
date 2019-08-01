import re
import ast
import sys
from docutils import nodes
import json
import astpretty
from stringcase import camelcase
import logging
import builtins

def comments_for(node):
    return []
    return [{'type': 'CommentBlock', 'value': 'line = %d' % node.lineno }]

class ValueCollector(ast.NodeVisitor):
    in_class_def = False
    enabled = False
    disable_perm = False
    data = None
    context = None
    append_to = None
    collected_value = None
    main_node = None
    body = None
    collect_array = None
    collect_scalar = None
    main_collect_array = None
    main_collect_scalar = None
    stack = None
    in_stmt = False
    do_camelcase = True
    def __init__(self, name, enabled=False, do_camelcase=True):
        self.logger = logging.getLogger('assign')
        self.var_scope = { }
        self.body = []
        self.stack= []
        self.context = []
        self.append_to = []
        self.data = {}
        self.do_camelcase = do_camelcase
        self.name = name
        self.enabled = enabled
        if enabled:
            self.append_to = []

    def generic_visit(self,  node, callSuper=True, newStack=False):
        if self.enabled:
            self.logger.debug('%s', node.__class__.__name__)
            if self.main_node is None:
                self.main_node = node
                self.main_collect_array = self.collect_array
                self.main_collect_scalar = self.collect_scalar
        if newStack:
            self.logger.debug('creating new stack')
            self.stack.append(self.body)
            self.body = []
        if callSuper:
            super().generic_visit(node)
        if newStack:
            self.result = self.body
            self.logger.debug('popping stack %d' % len(self.result))
            self.body = self.stack.pop()
        if self.main_node == node:
            self.collected_value = self.append_to
    
    def visit_Assign(self, node):
        t = node.targets;
        if self.disable_perm:
            self.generic_visit(node)
            return
        oldEnabled = self.enabled
        self.enabled = True

        vvc = ValueCollector('assign.value', True)
        vvc.visit(node.value)
        try:
            v = vvc.collected_value
            if vvc.main_collect_array:
                value = { 'type': 'ArrayExpression',
                          'elements': vvc.collected_value }
            elif vvc.main_collect_scalar:
                if len(v) == 0:
                    self.logger.error('%s', astpretty.pformat(node.value))
                    exit(1)
                    
                value = v[0]
            else:
                self.logger.error('%s', astpretty.pformat(node.value))
                exit(4)

        except Exception as ex:
            raise ex;
        
        self.append_to = []
        self.generic_visit(node, False)
        right = value
        annotation = None
        if right['type'] == 'StringLiteral':
            annotation = { 'type': 'TSTypeAnnotation', 'typeAnnotation': { 'type': 'TSStringKeyword'} }
                
        self.logger.error("%r", right)
        while len(t):
            target = t.pop(0)
            tc = ValueCollector('target', True)
            tc.visit(target)
            val = tc.collected_value[0]
            if val['type'] == 'Identifier':
                n = val['name']
                self.logger.error('name is %s', n)
                var = self.find_var(val)
                if var is None:
                    self.logger.error('here')
                    self.register_var(val)
                    if annotation is not None:
                        val['typeAnnotation'] = annotation;
                    val = { 'type': 'VariableDeclaration', 'declarations': [{'type': 'VariableDeclarator', 'id': val }], 'kind': 'let' }

            left = val
            right = { 'type': 'AssignmentExpression',
                     'operator': '=',
                     'left': left,
                     'right': right,
                     }
        stmt = { 'type': 'ExpressionStatement', 'expression': right }
        self.body.append(stmt)
#        self.disable_perm = True
        self.enabled = oldEnabled

    def visit_Tuple(self, node):
        if not self.enabled:
            self.generic_visit(node)

        self.context.append(self.append_to)
        self.append_to = []
        self.collect_scalar = True
        self.generic_visit(node)
        expr = { "type": 'CallExpression', 'callee': { 'type': 'Identifier', 'name': 'Tuple'}, 'arguments': self.append_to, 'comments': comments_for(node) }

        self.append_to = self.context.pop()
        self.append_to.append(expr)

    def visit_List(self, node):
        if not self.enabled:
            self.generic_visit(node)
        if self.append_to is not None:
            self.context.append(self.append_to)

        self.collect_array = True
        self.append_to = []
        self.generic_visit(node)
        expr = { "type": 'ArrayExpression', 'elements': self.append_to, 'comments': comments_for(node) }
        if len(self.context) > 0:
            self.append_to = self.context.pop()
            self.append_to.append(expr)
        else:
            raise Exception()

    def visit_Num(self,node):
        if not self.enabled:
            self.generic_visit(node)
            return
        self.collect_scalar = True
        self.append_to.append({ 'type': 'NumericLiteral', 'value': node.n });
        self.generic_visit(node, False)

    def visit_Str(self,node):
        if not self.enabled:
            self.generic_visit(node)
            return
        self.collect_scalar = True
        self.append_to.append({ 'type': 'StringLiteral', 'value': node.s });
        self.generic_visit(node)

    def visit_Name(self, node):
        if not self.enabled:# or not isinstance(node.ctx, ast.Load):
            self.generic_visit(node)
            return
        if node.id == 'self':
            expr= { 'type': 'ThisExpression' }
        else:
            expr= { 'type': 'Identifier', 'name': camelcase(node.id) if self.do_camelcase and not re.match('__', node.id) else node.id }
        self.append_to.append(expr)
        self.collect_scalar = True
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if not self.enabled:## or not isinstance(node.value, ast.Name) or not isinstance(node.value.ctx, ast.Load):
            self.generic_visit(node)
            return

        v = ValueCollector('attribute.value', True)
        v.visit(node.value)
        object = v.collected_value[0]


        id_name = camelcase(node.attr) if self.do_camelcase and not re.match('__', node.attr) else node.attr
        expr = { 'type': 'MemberExpression',
                 'object': object,
                 'property': { 'type': 'Identifier', 'name': id_name },
                 'comments': comments_for(node) }
        self.append_to.append(expr)
        self.collect_scalar = True
        self.generic_visit(node, False)

    def visit_UnaryOp(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return
        operator = None
        if isinstance(node.op, ast.Not):
            operator = '!'
        elif isinstance(node.op, ast.USub):
            operator = '-'
        else:
            self.logger.error('%s', astpretty.pformat(node.value))
            exit(5)

        self.context.append(self.append_to)
        self.append_to = []
        self.collect_scalar = True
        self.generic_visit(node)
        expr = { 'type': 'UnaryExpression', 'operator': operator, 'argument': self.append_to[0], 'prefix': True }
        self.append_to = self.context.pop()
        self.append_to.append(expr)
    def visit_If(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return
        v = ValueCollector('', True)
        v.visit(node.test)
        if not v.main_collect_scalar:
            self.logger.error('%s', astpretty.pformat(node.test))
            exit(6)

        test = v.collected_value[0]

        body= []
        for stmt in node.body:
            v2 = ValueCollector('', True)
            
            v2.visit(stmt)
            body.extend(v2.body)

        orelse= []
        for stmt in node.orelse:
            v3 = ValueCollector('', True)
            v3.visit(stmt)
            orelse.extend(v3.body)

        expr = { 'type': 'IfStatement', 'test': test, 'consequent':{ 'type': 'BlockStatement', 'body': body } }
        if len(orelse):
            expr['alternate'] = { 'type': 'BlockStatement', 'body': orelse }
        self.body.append(expr)
        

    def visit_BoolOp(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return
        vals = []
        for value in node.values:
            vc = ValueCollector('boolop.value', True)
            vc.visit(value)
            if not vc.main_collect_scalar:
                print('x:', astpretty.pformat(value))
                exit(6)
                
            v = vc.collected_value[0]
            vals.append(v)

        operator = None
        if isinstance(node.op, ast.Or):
            operator = '||'
        elif isinstance(node.op, ast.And):
            operator = '&&'
        else:
            print(astpretty.pformat(node))
            exit(3)
        
        left = vals.pop(0)
        while len(vals):
            left = { 'type': 'LogicalExpression', 'operator': operator, 'left': left, 'right': vals.pop(0) }
        self.append_to.append(left)
        self.collect_scalar = True
        self.generic_visit(node, False)

    def visit_BinOp(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return
        v = ValueCollector("left binop", True)
        v.visit(node.left)
        if v.main_collect_array:
            left = { 'type': 'ArrayExpression', 'elements': v.collected_value }
        else:
            left = v.collected_value[0]

        v2 = ValueCollector("right binop", True)
        v2.visit(node.right)
        if v2.main_collect_array:
            right = { 'type': 'ArrayExpression', 'elements': v2.collected_value }
        else:
            right = v2.collected_value[0]

        operator = None
        if isinstance(node.op, ast.Add):
            operator = '+'
        if isinstance(node.op, ast.Sub):
            operator = '-'
        if operator is not None:
            expr = { 'type': 'BinaryExpression', 'operator': operator, 'left': left, 'right': right, 'comments': comments_for(node) }
        else:
            expr = { 'type':'CallExpression', 'callee': { 'type':'Identifier', 'name': 'pyBinOp'}, 'arguments': [{ 'type': 'StringLiteral', 'value': node.op.__class__.__name__}, left, right], 'comments': comments_for(node)}
        self.append_to.append(expr)
        self.collect_scalar = True
        self.generic_visit(node, False)

    def visit_NameConstant(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return
        expr = None
        if node.value is None:
            expr = { 'type': 'TSUndefinedKeyword' }
        if node.value in (True, False):
            expr = { 'type': 'Literal', 'value': node.value }
        if expr is not None:
            self.cur_expr = expr
            self.append_to.append(expr)
            
        self.collect_scalar = True
        self.generic_visit(node)
        self.collect_scalar = None

    def visit_Dict(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return
        keys = []
        values = []
        for key in node.keys:
            kc = ValueCollector('key', True)
            kc.visit(key)
            assert kc.main_collect_scalar, 'scalar 2'
            key2 = kc.collected_value[0]
            keys.append(key2)
        for value in node.values:
            vc = ValueCollector('key', True)
            vc.visit(value)
            if not vc.main_collect_scalar:
                print('x:', astpretty.pformat(value))
                exit(7)
                
            value2 = vc.collected_value[0]
            values.append(value2)
        props = []
        for i in range(0, len(keys)):
            props.append({'type': 'Property', 'key': keys[i], 'value': values[i] })
            
        expr = { 'type': 'ObjectExpression', 'properties': props, 'comments': comments_for(node) }
        self.append_to.append(expr)
        self.collect_scalar = True
        self.generic_visit(node, False)
        

    def visit_Call(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return
        func_c = ValueCollector('func', True)
        func_c.visit(node.func)
        assert func_c.main_collect_scalar, 'func scalar'
        func = func_c.collected_value[0]
        args = []
        for arg in node.args:
            arg_c = ValueCollector('arg', True)
            arg_c.visit(arg)
            if arg_c.main_collect_array:
                value = { 'type': 'ArrayExpression',
                          'elements': arg_c.collected_value }
            elif arg_c.main_collect_scalar:
                value = arg_c.collected_value[0]
            else:
                print('b', astpretty.pformat(arg))
                exit(8)
            args.append(value)
        expr = None
        try:
            if func['type'] == 'Identifier':
                funcName = func['name']
                if builtins.__dict__[funcName]:
                    self.logger.info('found builtin %s', funcName)
            
                if funcName == "len":
                    assert len(args) == 1
                    expr = { 'type': 'MemberExpression',
                             'object': args[0],
                             'property': {'type':'Identifier', 'name':'length'},
                    }
                else:
                    args.insert(0, {'type':'StringLiteral', 'value': funcName })
                    expr = { 'type': 'CallExpression',
                             'callee': {'type': 'Identifier', 'name': '_pyBuiltin'},
                             'arguments': args }
        except KeyError:
            pass

        if expr is None:
            expr = { 'type': 'CallExpression',
                     'callee': func,
                     'arguments': args,
                     'comments': comments_for(node)
            }
        self.collect_scalar = True
        assert expr
        self.append_to.append(expr)
        self.generic_visit(node)

    def visit_Starred(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return
        self.collect_scalar = True
        vc = ValueCollector('value', True)
        vc.visit(node.value)
        assert vc.main_collect_scalar, 'scalar 4'
        argument = vc.collected_value[0]
        expr = { 'type': 'SpreadElement', 'argument': argument, 'comments': comments_for(node) }
        self.append_to.append(expr)
        self.generic_visit(node, False)

    def visit_Subscript(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return
        self.collect_scalar = True
        vc = ValueCollector('value', True)
        vc.visit(node.value)
        assert vc.main_collect_scalar, 'scalar 5'
        value = vc.collected_value[0]

        index = None
        if isinstance(node.slice, ast.Index):
            vc5 = ValueCollector('value', True)
            vc5.visit(node.slice.value)
            if not vc5.main_collect_scalar:
                print('zz', astpretty.pformat(node))
                exit(9)

                
            index = vc.collected_value[0]
            expr = { 'type': 'MemberExpression', 'object': value, 'property': index, 'comments': comments_for(node) }
        elif isinstance(node.slice, ast.Slice):
            lower = {'type':'NumericLiteral', 'value': 0}
            if node.slice.lower is not None:
                vc2 = ValueCollector('lower', True)
                vc2.visit(node.slice.lower)
                assert vc2.main_collect_scalar, 'scalaf 6'
                lower = vc2.collected_value[0]

            upper = None
            if node.slice.upper is not None:
                vc3 = ValueCollector('upper', True)
                try:
                    vc3.visit(node.slice.upper)
                except Exception as ex:
                    print(ex)
                    print('zzz', astpretty.pformat(node))
                    exit(10)

                    assert vc3.main_collect_scalar, 'scalar 8'
                    upper = vc3.collected_value[0]

            step = None
            if node.slice.step is not None:
                vc4 = ValueCollector('step', True)
                vc4.visit(node.slice.step)
                assert vc4.main_collect_scalar, 'scalar 9'
                step = vc3.collected_value[0]

            args = [lower]
            if upper is not None:
                args.append(upper)
                
            expr = { 'type':'CallExpression', 'callee': { 'type': 'MemberExpression', 'object': value, 'property': { 'type':'Identifier', 'name': 'slice' } }, 'arguments': args, 'comments': comments_for(node) }
            
        self.collect_scalar = True
        self.append_to.append(expr)
        self.generic_visit(node, False)

    def visit_ListComp(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return
        self.collect_scalar = True
        expr = { 'type': 'TSUndefinedKeyword', 'comments': comments_for(node) }
        self.append_to.append(expr)
        self.generic_visit(node, False)
    def visit_GeneratorExp(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return
        self.collect_scalar = True
        expr = { 'type': 'TSUndefinedKeyword' }
        self.append_to.append(expr)
        self.generic_visit(node, False)
    def visit_Compare(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return
        if len(node.ops) != 1:
            expr = { 'type': 'TSUndefinedKeyword' }
            self.append_to.append(expr)
            self.collect_scalar = True
            self.generic_visit(node)
            return
            
        assert len(node.ops) == 1, 'node ops 1'
        op = node.ops[0]
        operator = None
        negate = False
        if isinstance(op, (ast.Eq, ast.Is)):
            operator = '==='
        elif isinstance(op, (ast.In)):
            operator = 'in'
        elif isinstance(op, (ast.Gt)):
            operator = '>'
        elif isinstance(op, (ast.Lt)):
            operator = '<'
        elif isinstance(op, (ast.LtE)):
            operator = '<='
        elif isinstance(op, (ast.NotEq)):
            operator = '!=='
        elif isinstance(op, (ast.NotIn)):
            negate = True
            operator = 'in'
        else:
            print(astpretty.pformat(node))
            exit(2)
        
        comparator = node.comparators[0]
        v = ValueCollector("compator", True)
        v.visit(comparator)
        if v.main_collect_array:
            comparator = { 'type': 'ArrayExpression', 'elements': v.collected_value }
        else:
            comparator = v.collected_value[0]

        v2 = ValueCollector("left", True)
        v2.visit(node.left)
        if v2.main_collect_array:
            left = { 'type': 'ArrayExpression', 'elements': v2.collected_value }
        else:
            left = v2.collected_value[0]

        expr = { 'type': 'BinaryExpression', 'operator': operator, 'left': left, 'right': comparator, 'comments': comments_for(node) }
        if negate:
            expr = { 'type': 'UnaryExpression', 'operator': '!', 'prefix': True, 'operand': expr }
        self.append_to.append(expr)
        self.collect_scalar = True
        self.generic_visit(node, False)

    def visit_FunctionDef(self, node):
        assert isinstance(node.args, ast.arguments), 'args'
        args = []
        for arg in node.args.args:
            v = ValueCollector('functiondef', True)
            v.visit(arg)
            if not v.main_collect_scalar:
                print('x:', astpretty.pformat(arg))
                exit(11)
                
            args.append(v.collected_value[0])

        oldEnabled = self.enabled
        self.enabled = True
        self.generic_visit(node, True, True)
        self.enabled = oldEnabled


        expr = { 'type': 'FunctionDeclaration', 'params': args,
                 'id': { 'type': 'Identifier', 'name': node.name} ,
                 'body': { 'type': 'BlockStatement', 'body': self.result} }
        if self.in_class_def:
            expr['params'] = args[1:]
            expr['type'] = 'MethodDefinition'
            if node.name == "__init__":
                expr['kind'] = 'constructor'
                expr['key'] = { 'type': 'Identifier', 'name': 'constructor' }
            else:
                expr['kind'] ='method'
                expr['key'] = { 'type': 'Identifier', 'name': node.name }
        else:
            expr['name'] = node.name

        self.logger.info('%s' % astpretty.pformat(node).replace('\n', '  '))
        self.body.append(expr)

    def visit_arg(self, node):
        if not self.enabled:
            self.generic_visit(node)
            return
        self.collect_scalar = True
        expr = { 'type': 'Identifier', 'name': node.arg, 'comments': comments_for(node) }
        self.append_to.append(expr)
        self.generic_visit(node, False)

    def visit_ClassDef(self, node):
        oldEnabled = self.enabled
        assert not self.in_class_def
        self.in_class_def = True
        self.enabled = True
        self.generic_visit(node, True, True)
        self.enabled = oldEnabled
        #assert len(node.bases) in (0, 1)
        expr = { 'type': 'ClassDeclaration', 'id': { 'type': 'Identifier', 'name': node.name }, 'body': { 'type': 'ClassBody', 'body': self.result } }
        if len(node.bases):
            base = node.bases[0]
            v = ValueCollector('', True, do_camelcase=False)
            v.visit(base)
            assert v.main_collect_scalar
            b = v.collected_value[0]
            expr['superClass'] = b

        self.in_class_def = False
        self.body.append(expr)

    def visit_Expr(self, node):
        oldEnabled = self.enabled
        self.enabled = True
        self.context.append(self.append_to)
        self.append_to = []
        self.generic_visit(node, True)
        expr = { 'type': 'ExpressionStatement', 'expression': self.append_to[0] }
        self.append_to = self.context.pop()
        self.body.append(expr)
        self.enabled = oldEnabled

    def visit_Return(self, node):
        oldEnabled = self.enabled
        self.enabled = True
        self.context.append(self.append_to)
        self.append_to = []
        self.generic_visit(node, True)
        expr = { 'type': 'ReturnStatement', 'argument': self.append_to[0] }
        self.append_to = self.context.pop()
        self.body.append(expr)
        self.enabled = oldEnabled

    def find_var(self, node):
        assert node['type'] == 'Identifier'
        if node['name'] in self.var_scope:
            return self.var_scope[node['name']]
        return None

    def register_var(self, node):
        assert node['type'] == 'Identifier'
        assert node['name'] not in self.var_scope
        self.var_scope[node['name']] = node

    def report(self):
        pass
