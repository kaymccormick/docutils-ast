import json
import requests
import ast
class ApplicationError(Exception):
    def __init__(self, value, node=None):
        self.value = value
        self.node = node
    def __str__(self):
        return '%s: %s'% (self.value, ast.dump(self.node))

class Namespace(dict):
    pass


def check_ast(astnode):
    r = requests.post('http://localhost:7700/ast/check-ast', json={ 'astNode': astnode})
    if r.status_code == 200:
        return True
    if r.status_code == 401:
        raise ApplicationError(r.text)
    return False
    
