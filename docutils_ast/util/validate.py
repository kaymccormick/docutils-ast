def node_type(node):
    return node['type']

class ProgramValidator:
    def __init__(self, kinds, named_types, logger=None):
        self.logger = logger
        self.kinds = kinds
        self.named_types = named_types

    def process_type(self, type):
        accept = []
        py_accept = []
        type_kind = None
        if type['type'] == 'TSUnionType':
            for atype in type['types']:
                (a, p) = self.process_type(atype)
                accept.extend(a)
                py_accept.extend(p)
        elif type['type'] == 'TSTypeReference':
            t = type['typeName']
            self.process_type(t)
        elif type['type'] == 'TSQualifiedName':
            left = type['left']
            if left['type'] == 'Identifier' and left['name'] == 'K':
                type_kind = type['right']
            elif type['type'] == 'Identifier':
                if type['name'] == 'string':
                    py_type = str
                    py_accept.append(py_type)
        if type_kind:
            assert type_kind['type'] == 'Identifier'
            kind = type_kind['name']
            kind_info = self.kinds[kind]
            if isinstance(kind_info, str):
                # single mapped type
                accept.append(kind_info)
            else:
                accept.extend(kind_info)
        return (accept, py_accept)
            

    def validate_node(self, node, supertype=None):
        if supertype:
            n_type = self.named_types[supertype]
        else:
            n_type = self.named_types[node_type(node)]
        if 'extends' in n_type:
            for e in n_type['extends']:
                name = e['name']
                assert isinstance(name, str)
                self.validate_node(node, name)
                
        for field in n_type['fields']:
            print(field)
            name = field['name']
            print(node_type(node), name, list(field.keys())) 
            value = None
            type = None
            py_type = None
            if 'value' in field:
                value = field['value']
                assert node[name] == value
            else:
                type = field['type']
                is_array = node_type(type) == 'TSArrayType'
                if is_array:
                    elem_type = type['elementType']
                else:
                    elem_type = type
                (accept, py_accept) = self.process_type(type)
                
                v = None
                if name in node:
                    v = node[name]
                    print('v', repr(v), name, accept, py_accept)
                if v is None:
                    assert 'optional' in field and field['optional'], str(field)
                else:
                    if not is_array:
                        assert v in accept or isinstance(v, tuple(py_accept)), '%r, %s, %r' % (v, name, py_accept)
                    else:
                        for x in v:
                            assert v['type'] in accept
    def validate(self, file):
        assert file, 'input is undefined'
        assert node_type(file) == 'File'
        self.validate_node(file)
        
