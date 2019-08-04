import logging
import logging.config
import json
import sys
import argparse
from docutils_ast.process.translate import CodeTranslator

def main(*argv, logger_name='translate.py'):
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input-filename')
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

    t = CodeTranslator(logger=logger)
    t.translate(args.input_filename, args.output_filename)

