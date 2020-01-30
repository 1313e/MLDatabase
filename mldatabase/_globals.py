# -*- coding utf-8 -*-

"""
Globals
=======

"""


# %% IMPORTS
# Package imports
from os import path

# All declaration
__all__ = ['DIR_PATH', 'MASTER_FILE', 'MLD_NAME', 'N_OBJIDS', 'OBJID_NAME',
           'OBJS_FILE', 'PKG_NAME']


# %% PACKAGE GLOBALS
DIR_PATH = path.abspath(path.dirname(__file__))     # Path to this directory
MASTER_FILE = 'master.hdf5'                         # Name of master hdf5-file
MLD_NAME = '.mldatabase'                            # Name of database folder
N_OBJIDS = 10000                                    # Number of objids per file
OBJID_NAME = '{:0=9}'                               # Name/converter of objid
OBJS_FILE = f'objid{OBJID_NAME}_{OBJID_NAME}.hdf5'  # Name of objs hdf5-file
PKG_NAME = 'MLDatabase'                             # Name of package
