# -*- coding utf-8 -*-

"""
Globals
=======

"""


# %% IMPORTS
# Built-in imports
from os import path

# All declaration
__all__ = ['DIR_PATH', 'EXIT_KEYWORDS', 'EXP_HEADER', 'EXP_REGEX',
           'MASTER_EXP_FILE', 'MASTER_FILE', 'MLD_NAME', 'PKG_NAME',
           'REQ_FILES', 'SIZE_SUFFIXES', 'TEMP_EXP_FILE', 'XTR_HEADER']


# %% PACKAGE GLOBALS
DIR_PATH = path.abspath(path.dirname(__file__))     # Path to this directory
EXIT_KEYWORDS = ['exit',                            # Exit prompt keywords
                 'exit()',
                 'quit',
                 'q']
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
SIZE_SUFFIXES = ['bytes',                           # File size suffixes
                 'KiB',
                 'MiB',
                 'GiB',
                 'TiB',
                 'PiB',
                 'EiB',
                 'ZiB',
                 'YiB']
TEMP_EXP_FILE = 'temp_exp{}.hdf5'                   # Name of temp exp file
XTR_HEADER = {                                      # Header of xtr/epochs file
    'expnum': int,
    'hjd': float,
    'skypc2': float,
    'skypc5': float,
    'skypc10': float,
    'skypc90': float,
    'filter': '|S10',
    'fitsname': '|S80'}
