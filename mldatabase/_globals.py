# -*- coding utf-8 -*-

"""
Globals
=======

"""


# %% IMPORTS
# Package imports
from os import path

# All declaration
__all__ = ['DIR_PATH', 'MLD_NAME', 'PKG_NAME']


# %% PACKAGE GLOBALS
DIR_PATH = path.abspath(path.dirname(__file__))     # Path to this directory
MLD_NAME = '.mldatabase'                            # Name of database folder
PKG_NAME = 'MLDatabase'                             # Name of package
