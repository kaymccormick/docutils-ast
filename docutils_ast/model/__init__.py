import sys
import logging

logger = logging.getLogger('model')

class ModelElement:
    pass

class NamedElement:
    pass

class Namespace(ModelElement):
    def __init__(self):
        super().__init__()
        self.namespace = {}


    def name_exists(self, name: str) -> bool:
        return name in self.namespace
    
    def get_name(self, name: str):
        if name in self.namespace:
            return self.namespace[name]
        return None

    def store_name(self, name: str, elem: NamedElement):
        print('storing name %s' % name, file=sys.stderr)
        if name == 'document':
            print('storing name %s' % name, file=sys.stderr)
            
        self.namespace[name] = { 'elem': elem }

class Class(Namespace, NamedElement):
    def __init__(self, name: str, node=None):
        super().__init__()
        self.name = name
        self.node = node
        self.elems = []

    def add(self, elem):
        self.elems.append(elem)

    def __repr__(self):
        return 'Class<%s>' % self.name

class Module(Namespace):
    def __init__(self, file: str = None):
        super().__init__()
        self.file= file

class ClassProperty(NamedElement):
    def __init__(self, class_: Class, name: str):
        self.class_ = class_
        self.name = name
    def ast_node(self):
        return dict(type='ClassProperty', key=dict(type='Identifier',name=self.name), access='public', typeAnnotation=dict(type='TSTypeAnnotation', typeAnnotation=dict(type='TSAnyKeyword')))
