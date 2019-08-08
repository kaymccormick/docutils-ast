import json
import requests
import ast
class ApplicationError(Exception):
    message = None
    def __init__(self, message, node=None):
        self.message = message
        self.node = node
        self.lineno = None
    def __str__(self):
        return '%s[%s]%s' % (self.message, str(self.lineno), (' ' + ast.dump(self.node)) if self.node else '')

class Namespace(dict):
    pass


def check_ast(astnode):
    r = requests.post('http://localhost:7700/ast/check-ast', json={ 'astNode': astnode})
    if r.status_code == 200:
        return r.text
    if r.status_code == 401:
        raise ApplicationError(r.text)
    return False
    
