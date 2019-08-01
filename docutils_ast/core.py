from pathlib import Path

docutils_dir = './venv/lib/python3.7/site-packages/docutils'
docutils_path = Path(docutils_dir)
docutils_files = list(docutils_path.glob('**/*.py'))
_files = {}
for file in docutils_files:
    _files[file] = file

print(_files)

def get_tree(path):
    with path.open('r') as source:
        return ast.parse(source.read())
