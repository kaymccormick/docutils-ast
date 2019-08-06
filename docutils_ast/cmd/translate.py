import tempfile
import logging
import logging.config
import json
import sys
import argparse
import subprocess
from docutils_ast.process.translate import CodeTranslator
from docutils_ast.util.validate import ProgramValidator

def main(*argv, logger_name='translate.py'):
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input-filename')
    parser.add_argument('-j', '--json-filename')
    parser.add_argument('-o', '--output-filename')
    if not len(argv):
        argv = sys.argv[1:]
    args = parser.parse_args(argv)
    if args.input_filename:
        file = args.input_filename

    try:
        logging.config.fileConfig('logging.conf')
    except Exception as ex:
        print(str(ex), file=sys.stderr)
        exit(1)

    logger = logging.getLogger(logger_name)
    with open('files/kinds.json', 'r') as f:
        kinds = json.load(fp=f)
    with open('files/namedTypes.json', 'r') as f:
        named_types = json.load(fp=f)

    t = CodeTranslator(kinds, named_types, logger=logger)
    program = t.translate(args.input_filename, args.json_filename)
    v = ProgramValidator(kinds, named_types, logger=logger)
    #v.validate(program)
    
    completed = subprocess.run(('node', '/local/home/jade/JsDev/shift-t/lib/bin/translate.js', '-i', args.json_filename, '-o', 'out.ts'), capture_output=True)
    sys.stdout.write(completed.stdout.decode())
    sys.stderr.write(completed.stderr.decode())
    completed.check_returncode()

if __name__ == '__main__':
    main(*sys.argv[1:], logger_name='translate.py')
