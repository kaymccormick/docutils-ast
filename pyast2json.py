import ast
import sys
from lxml import etree
import astpretty
import pprint

python_ns = 'http://heptet.us/lang/python'
node_ns = 'http://heptet.us/lang/python/ast/node'
field_ns = 'http://heptet.us/lang/python/ast/field'
builtins_ns = 'http://heptet.us/lang/python/builtins'

NSMAP = { None: node_ns,
          'field': field_ns,
          'python': python_ns,
          'builtins': builtins_ns,
          }

class Visitor(ast.NodeVisitor):
    def __init__(self):
        self.elements = []
        self.lastElement = None
        self.cur_element = None
        self.fields = []

    def visit_Tuple(self, node):
        print("x", astpretty.pformat(node), file=sys.stderr)
        self.generic_visit(node)

    def generic_visit(self, node):
        try:
            tagname = node.__class__.__name__
            tagname = '{http://heptet.us/lang/python/ast/node}' + tagname
 #           print(tagname)
            if len(self.elements):
                element = etree.SubElement(self.elements[-1], tagname)
            else:
                element = etree.Element(tagname, nsmap=NSMAP)

            attrib = {}
            for k,value in ast.iter_fields(node):
                if isinstance(value, ast.expr_context):
                    element.attrib[k] = value.__class__.__name__
                    attrib[k] = True
                if not isinstance(value, (list, ast.AST)):
                    if value is not None:
                        try:
                            element.attrib['{http://heptet.us/lang/python/ast/field}' + k] = str(value)
                            attrib[k] = True
                        except ValueError as val_error:
                            #print(repr(value))
                            pass
            #print(tagname)
            self.elements.append(element)

            #fields_elem = etree.SubElement(element, 'fields')
            for field, value in ast.iter_fields(node):
                if field not in attrib:
                    attr = dict()
                    if value.__class__.__module__ == 'builtins':
                        attr['{' + builtins_ns + '}' + value.__class__.__name__] = "true"
                    else:
                        attr['{' + python_ns + '}type'] = value.__class__.__module__ + '.' + value.__class__.__name__

                    field_elem = etree.SubElement(self.elements[-1], '{http://heptet.us/lang/python/ast/field}' + field, **attr)
                    self.elements.append(field_elem)
                    if isinstance(value, list):
                        #value_list = etree.SubElement(self.elements[-1], 'ValueList')
                        #self.elements.append(value_list)
                        for item in value:
                            if isinstance(item, ast.AST):
                                self.visit(item)
                        #self.elements.pop()
                    elif isinstance(value, ast.AST):
#                        value_elem = etree.SubElement(self.elements[-1], 'Value')
#                        self.elements.append(value_elem)
                        self.visit(value)
#                        self.elements.pop()
    
                    self.elements.pop()
                #self.elements.pop()
            if(len(self.elements) > 1):
#                print("pop")
                elem = self.elements.pop(-1)
            else:
                pass
#                print("nopop")

        except Exception as err:
            raise err
            pprint.pprint(err, stream=sys.stderr)



file = sys.argv[1]
with open(file, 'r') as source:
    tree = ast.parse(source.read());

v = Visitor()
v.visit(tree)
elements = v.elements
if not len(elements):
    raise Exception("dohh")

#print(elements[0])
print(etree.tostring(elements[0]).decode('utf-8'))
