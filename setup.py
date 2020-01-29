# -*- coding: utf-8 -*-

"""
Setup file for the *MLDatabase* package.

"""


# %% IMPORTS
# Built-in imports
from codecs import open
import re

# Package imports
from setuptools import find_packages, setup


# %% SETUP DEFINITION
# Get the long description from the README file
with open('README.rst', 'r') as f:
    long_description = f.read()

# Get the requirements list
with open('requirements.txt', 'r') as f:
    requirements = f.read().splitlines()

# Read the __version__.py file
with open('mldatabase/__version__.py', 'r') as f:
    vf = f.read()

# Obtain version from read-in __version__.py file
version = re.search(r"^_*version_* = ['\"]([^'\"]*)['\"]", vf, re.M).group(1)

# Setup function declaration
setup(name="mldatabase",
      version=version,
      author="Ellert van der Velden",
      author_email='evandervelden@swin.edu.au',
      description=(""),
      long_description=long_description,
      url='https://www.github.com/1313e/MLDatabase',
      license='BSD-3',
      platforms=["Windows", "Linux", "Unix"],
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: BSD License',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: Unix',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Topic :: Software Development :: Libraries :: Python Modules',
          'Topic :: Utilities',
          ],
      keywords=('python'),
      python_requires='>=3.6, <4',
      packages=find_packages(),
      package_dir={'mldatabase': "mldatabase"},
      entry_points={
          'console_scripts': [
              "mld = mldatabase.__main__:main"]},
      include_package_data=True,
      install_requires=requirements,
      zip_safe=False,
      )
