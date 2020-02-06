# -*- coding utf-8 -*-

"""
Globals
=======

"""


# %% IMPORTS
# Package imports
from os import path

# All declaration
__all__ = ['DIR_PATH', 'EXP_HEADER', 'EXP_REGEX', 'MASTER_EXP_FILE',
           'MASTER_FILE', 'MLD_NAME', 'PKG_NAME', 'REQ_FILES']


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
MASTER_EXP_FILE = 'exp_master.hdf5'                 # Name of master exp file
MLD_NAME = '.mldatabase'                            # Name of database folder
PKG_NAME = 'MLDatabase'                             # Name of package
REQ_FILES = ['Exp0.csv', 'Exp0_xtr.csv']            # Exposure files required
