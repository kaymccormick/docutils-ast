from setuptools import setup, find_packages

setup(version='0.0.1',
      name='docutils-ast',
      packages=find_packages(),
      entry_points={
          'console_scripts': [
          'translate = docutils_ast.cmd.translate:main'
          ]
          }
)
