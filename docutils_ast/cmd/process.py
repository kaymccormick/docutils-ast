import json
import re
import ast
from pprint import pprint
from sys import stderr
import logging
import astpretty

import logging.config

def main():
    logging.config.fileConfig('logging.conf')

    MAXDEBUG = 10
    debug = MAXDEBUG
    mainout = open('out.txt', 'w')
    
    class VisitFunctionDefAnalyzer(ast.NodeVisitor):
        def __init__(self, node_arg, node_name, kind):
            self.node_arg = node_arg
            self.node_name = node_name
            self.kind = kind
            self.self_arg = 'self'
            self.context = []
            self.classes_vars = []
            self.logger = logging.getLogger('funcdef')
            self.logger.setLevel(logging.DEBUG)
    
        def generic_visit(self,  node):
            self.context.append(node)
            super().generic_visit(node)
    
        def generic_depart(self, node):
            self.context.pop()
            super().generic_depart(node)
            
        def visit_Call(self, node):
            if not isinstance(node.func, ast.Name):
                if isinstance(node.func.value, ast.Attribute):
                    if isinstance(node.func.value.value, ast.Name):
                        if node.func.value.value.id == self.self_arg:
                            if node.func.value.attr == 'body' and node.func.attr == 'append':
                                arg = node.args[0]
                                line = '%s %r body.append(' % (self.kind, self.node_name)
                                if isinstance(arg, ast.Str):
                                    line += '%r)' % arg.s
                                else:
                                    line += '%s' % ast.dump(arg)
                                    
                                self.logger.info('%s', line)
                elif isinstance(node.func.value, ast.Name):
                    varname = node.func.value.id
                    if varname in self.classes_vars:
                        self.logger.info("XXX %s" % ast.dump(node))
                    elif varname == self.self_arg:
                        self.logger.info('%s', ast.dump(node))
                        if node.func.attr == 'body':
                            self.logger.info('%s', ast.dump(node.func))
                            if node.func.attr == 'append':
                                self.logger.info('%s', ast.dump(node.func.args[0]))
                                
                    elif node.func.value.id == self.node_arg:
                        if node.func.attr == 'setdefault':
                            if node.args[0].s == 'classes':
                                assign = self.context[-3]
                                vars = []
                                if isinstance(assign, ast.Assign):
                                    for target in assign.targets:
                                        if(isinstance(target, ast.Name)):
                                            vars.append(target.id)
                                            self.classes_vars = vars
                                            self.initial_classes = node.args[1]
                                            self.logger.debug(ast.dump(assign))
                                            self.generic_visit(node)
    
    #    def visit_Call(self, node):
    #        self.logger.debug(ast.dump(node))
    #        if isinstance(node.func, ast.Name):
    #            pass
    #        elif isinstance(node.func.value, ast.Name) and node.func.value.id in self.classes_vars:
    #            self.logger.debug("XXX %s" % ast.dump(node))
    #        self.generic_visit(node)
            
    
    def node2name(node):
        if isinstance(node, ast.Attribute):
            thing = node.attr
        elif isinstance(node, ast.Subscript):
            thing = node.value
        elif isinstance(node, ast.Name):
            thing = node.id
        elif isinstance(node, ast.Str):
            thing = node.s
        else:
            thing = node.__class__.__name__
        return (thing, node.__class__.__name__)
    
    debug = False
    
    methodRgxp = re.compile('(visit|depart)_(.*)$')
    impBases = ['Element', 'FixedTextElement', 'Inline', 'Node', 'TextElement']
    
    class Analyzer(ast.NodeVisitor):
        def __init__(self):
            self.inMethod = None 
            self.visitNodeName = None
            self.node_var_name = None
            subTypes = {}
            for base in impBases:
                subTypes[base] = []
                self.stats = {"import": [], "from": [], "class": [], 'bases': {},
                              'subTypes': subTypes, 'nonLeafClasses': {},
                              'elements': {}}
    
        def visit_FunctionDef(self, node):
            match = methodRgxp.match(node.name)
            if match:
                kind = match.group(1)
                self.inMethod = node.name
                self.visitNodeName = match.group(2)
                self.kind = kind
                logging.debug('%s %s' % (kind, ast.dump(node)))
                self.node_var_name = None
                if len(node.args.args) >= 2:
                    self.node_var_name = node.args.args[1].arg
                    # print("setting inMethod to", node.name)
                    # print("found %s for %s" % (node.name, self.inClass))
                self.sub = VisitFunctionDefAnalyzer(self.node_var_name, self.visitNodeName, kind)
                self.sub.visit(node)
                self.generic_visit(node)
        def depart_FunctionDef(self, node):
            self.inMethod = None
            self.generic_depart(node)
    
        def visit_Assign(self, node):
            for target in node.targets:
                logging.debug('target=%s' % list(node2name(target))[0])
                
            self.generic_visit(node)
    
        def visit_Call(self, node):
            self.generic_visit(node)
            #        print("!", node)
            if not self.inMethod:
                return
    
            (name, what) = node2name(node.func)
            #print(node.func.__dir__())
            #print("clas of node.fnc",node.func.__class__.__name__)
            try:
                (thing, thingwhat) = node2name(node.func.value)
            except:
                thing = 'unknown'
                thingwhat = None
    
            fullspec = "%s.%s" % (thing, name)
            logging.debug("fullspec: %s" %fullspec)
            if(fullspec == 're.compile'):
                logging.debug('%s', node.args[0].s)
            elif(fullspec == 'self.starttag'):
                ary =self.stats['elements'].setdefault(self.visitNodeName, [])
                i = 0
                for arg in node.args:
                    logging.debug("%s" % ast.dump(arg))
                    #print("Z",arg.__class__.__name__)
                    #print("Z",arg.__dir__())
                    (name2, what2) = node2name(arg)
                    logging.debug("what2[%d] %s %s" %(i, name2, what2))
                    i+=1
    
                k = {}
                i = 0
                for arg in node.keywords:
                    logging.debug("z %d %s" % (i,ast.dump(arg)))
                    logging.debug(arg.arg)
                    if arg.arg:
                        k[arg.arg] = list(node2name(arg.value))[0]
                    else:
                        logging.debug("%s" % list(node2name(arg.value))[0])
                        logging.debug("%s" % ast.dump(arg.value.ctx))
                        i+=1
    
                if('suffix' in k):
                    del k['suffix']
                if 'empty' in k:
                    del k['empty']
    
                class_ = ''
                if 'CLASS' in k:
                    class_ = k['CLASS']
    
                #if(len(node.args) >= 3):
                #    ary.append(node.args[1].s)
                #else:
                (arg2, argwhat2) = node2name(node.args[1])
                ary.append(arg2)
                
                print("xml <%s/> -> HTML <%s %s>" %
                      (self.visitNodeName,
                       list(node2name(node.args[1]))[0],
                       ' '.join(map(lambda key: '%s="%s"' % (key.lower() if key else 'None', k[key]), k.keys()))),
                      file=mainout)
    
                    
        def visit_ClassDef(self, node):
            bases = []
            for base in node.bases:
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
            
    
        def depart_ClassDef(self, node):
            self.inClass = None
            self.generic_depart(node)
    
        def visit_Import(self, node):
            for alias in node.names:
                self.stats["import"].append(alias.name)
                self.generic_visit(node)
    
    #Assign(targets=[Subscript(value=Name(id='atts', ctx=Load()), slice=Index(value=Str(s='class')), ctx=Store())], value=Str(s='simple'))
        def generic_visit(self, node):
            #if not isinstance(node, (ast.Module, ast.ClassDef)):
            if isinstance(node, (ast.Module)):
                logging.debug('%s', astpretty.pprint(node))
                super().generic_visit(node)
                #        print(node)
            
        def visit_ImportFrom(self, node):
            for alias in node.names:
                self.stats["from"].append(alias.name)
                self.generic_visit(node)
    
        def report(self):
            #        for classObj in self.stats['class']:
            #            if(classObj['name'] in self.stats['nonLeafClasses']):
            #                self.stats['class'].pop(classObj['name'])
    
            items = list(self.stats['subTypes'].items())
            for name, val in items:
                #print(name)
                newval = []
                for base in val:
                    if self.stats['nonLeafClasses'].get(base, 0):
                        self.stats['subTypes'][name].remove(base)
                        
            self.stats.pop('bases')
            pprint(self.stats)
            
    
    docutils_dir = 'venv/lib/python3.7/site-packages/docutils/'
    file = docutils_dir + '/writers/_html_base.py'
    
    with open(file, 'r') as source:
        tree = ast.parse(source.read());
    
    analyzer = Analyzer();
    analyzer.visit(tree)
    analyzer.report()
    with open('out.json', 'w') as outf:
        json.dump(analyzer.stats['elements'], fp=outf)
    
if __name__ == '__main__':
    main()
