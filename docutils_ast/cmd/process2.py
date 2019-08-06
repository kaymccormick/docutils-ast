import sys
import symtable
import json
import re
import ast
from pprint import pprint
from sys import stderr
import logging
import astpretty
from docutils_ast.visitor.assign import ValueCollector
from docutils_ast.visitor.collect import Collector
from docutils_ast.transform import Transform1
from docutils_ast.model import Module
from docutils_ast.logging import StructuredMessage
_ = StructuredMessage
import docutils_ast.model
import argparse
import logging.config

docutils_dir = '/local/home/jade/JsDev/docutils-monorepo/docutils-ast/venv/lib/python3.7/site-packages/docutils/'

def main(argv, logger_name="process2.py"):
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input-filename')
    parser.add_argument('-o', '--output-filename')
    args = parser.parse_args(argv)
    if args.input_filename:
        file = args.input_filename

    db_credentials = { "database":"logs","host":"localhost","user":"logs","password":"poopfact"}
    
    try:
        logging.config.fileConfig('logging.conf')
    except Exception as ex:
        print(e.message, fp=sys.stderr)
        exit(1)
        pass

#    with open('out.json', 'w') as fp:
#        json.dump(analyzer.body, fp=fp, indent=4)

#    with open('out.json', 'w') as outf:
#        json.dump(analyzer.stats['elements'], fp=outf)
    
if __name__ == '__main__':
    print(dir())
    main(sys.argv[1:], logger_name='process2')
