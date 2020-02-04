# -*- coding utf-8 -*-

"""
Globals
=======

"""


# %% IMPORTS
# Package imports
from os import path

# All declaration
__all__ = ['DIR_PATH', 'EXP_HEADER', 'EXP_REGEX', 'MASTER_FILE', 'MLD_NAME',
           'N_OBJIDS', 'OBJID_NAME', 'OBJS_BIN', 'OBJS_FILE', 'PKG_NAME',
           'REQ_FILES']


# %% PACKAGE GLOBALS
DIR_PATH = path.abspath(path.dirname(__file__))     # Path to this directory
EXP_HEADER = {                                      # Header of exposure file
    'objid': int,
    'hjd': float,
    'ra': float,
    'decl': float,
    'mag': float,
    'magerr': float,
    'type': float,
    'contam': float,
    'chp': float,
    'xp': float,
    'yp': float,
    'bfloor': float,
    'moffset': float,
    'fitsky': float,
    'errlim': float,
    'expnum': int}
# Regex for finding exposure CSV-files
EXP_REGEX = (r"(?P<exp_file>(?P<base>Exp(?=\d*[1-9])(?P<expnum>\d+))\.csv)."
             r"*?(?P<xtr_file>(?P=base)_(xtr|epochs)\.csv)")
MASTER_FILE = 'master.hdf5'                         # Name of master hdf5-file
MLD_NAME = '.mldatabase'                            # Name of database folder
N_OBJIDS = 10000                                    # Number of objids per file
OBJID_NAME = '{:0=9}'                               # Name/converter of objid
OBJS_BIN = f'{OBJID_NAME}-{OBJID_NAME}'             # Name of objs bin
OBJS_FILE = f'objid{OBJID_NAME}_{OBJID_NAME}.hdf5'  # Name of objs hdf5-file
PKG_NAME = 'MLDatabase'                             # Name of package
REQ_FILES = ['Exp0.csv', 'Exp0_xtr.csv']            # Exposure files required
