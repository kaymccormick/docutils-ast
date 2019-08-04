def main(argv, logger_name='translate.py'):
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input-filename')
    parser.add_argument('-o', '--output-filename')
    args = parser.parse_args(argv)
    if args.input_filename:
        file = args.input_filename

    try:
        logging.config.fileConfig('logging.conf')
    except Exception as ex:
        print(e.message, fp=sys.stderr)
        exit(1)

    logger = logging.getLogger(logger_name)
