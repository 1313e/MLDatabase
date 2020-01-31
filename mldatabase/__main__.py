# -*- coding: utf-8 -*-

# %% IMPORTS
# TODO: Use 'argcomplete'?
# Built-in imports
import argparse
import os
from os import path
import re
import sys
from textwrap import dedent

# Package imports
import h5py
import pandas as pd
import numpy as np
from numpy.lib.arraysetops import setdiff1d, union1d

# MLDatabase imports
from mldatabase import (
    __version__, EXP_HEADER, EXP_REGEX, MASTER_FILE, MLD_NAME, N_OBJIDS,
    OBJID_NAME, OBJS_FILE, PKG_NAME, REQ_FILES)

# All declaration
__all__ = ['main']


# %% GLOBALS
# Define the main help docstring
main_description = dedent("")


# %% CLASS DEFINITIONS
# Define formatter that automatically extracts help strings of subcommands
class HelpFormatterWithSubCommands(argparse.ArgumentDefaultsHelpFormatter):
    # Override the add_argument function
    def add_argument(self, action):
        # Check if the help of this action is required
        if action.help is not argparse.SUPPRESS:
            # Check if this action is a subparser's action
            if isinstance(action, argparse._SubParsersAction):
                # If so, loop over all subcommands defined in the action
                for name, subparser in action.choices.items():
                    # Format the description of this subcommand and add it
                    self._add_item(self.format_subcommands,
                                   [name, subparser.description])
            # Call super method in all other cases
            else:
                super().add_argument(action)

    # This function formats the description of a subcommand with given name
    def format_subcommands(self, name, description):
        # Determine the positions and widths of the help texts
        help_position = min(self._action_max_length+2, self._max_help_position)
        help_width = max(self._width-help_position, 11)
        name_width = help_position-self._current_indent-2

        # Transform name to the proper formatting
        name = "{0}{1: <{2}}{3}".format(
                ' '*self._current_indent, name, name_width,
                '  ' if(len(name) <= name_width) else '\n'+' '*help_position)

        # Split the lines of the subcommand description
        desc_lines = self._split_lines(description, help_width)

        # Create list of all parts of the description of this subcommand
        parts = [name, desc_lines.pop(0), '\n']

        # Loop over all remaining desc_lines
        for line in desc_lines:
            # Format and add to parts
            parts.append("%s%s\n" % (' '*help_position, line))

        # Convert to a single string and return
        return(''.join(parts))


# %% COMMAND FUNCTION DEFINITIONS
# This function handles the 'init' subcommand
def init(args):
    # Check if a database already exists in this folder
    if path.exists(args.mld):
        # If so, raise error and exit
        print("ERROR: Provided DIR %r already contains a micro-lensing "
              "database!" % (args.dir))
        sys.exit()

    # Check if these files are present
    for req_file in REQ_FILES:
        if not path.exists(path.join(args.dir, req_file)):
            # If not, raise error and exit
            print("ERROR: Provided DIR %r does not contain required files for "
                  "micro-lensing database!" % (args.dir))
            sys.exit()

    # Make the database directory
    os.mkdir(args.mld)

    # Update the database
    update(args)


# This function handles the 'update' subcommand
def update(args):
    # Check if a database already exists in this folder
    if not path.exists(args.mld):
        # If not, raise error and exit
        print("ERROR: Provided DIR %r does not contain a micro-lensing "
              "database!" % (args.dir))
        sys.exit()

    # Obtain path to reference exposure file
    ref_exp_file = path.join(args.dir, 'Exp0.csv')

    # Read in the first column of this file (which should be all objids)
    objids = pd.read_csv(ref_exp_file, skipinitialspace=True, header=None,
                         names=EXP_HEADER, usecols=['objid'], squeeze=True,
                         dtype=np.int64, nrows=10000)

    # If objids contains no elements, raise error and exit
    if objids.empty:
        print("ERROR: Reference exposure file %r contains no objects!"
              % (ref_exp_file))
        sys.exit()

    # Convert objids to NumPy array
    objids = objids.to_numpy()

    # Open the master HDF5-file, creating it if it does not exist yet
    master_name = path.join(args.mld, MASTER_FILE)
    with h5py.File(master_name, mode='a') as m_file:
        # Obtain the known objids
        objids_known = m_file.get('objids', np.array([], dtype=int))
        n_objids_known = len(objids_known)

        # Take the difference and union between objids and the known ones
        objids = setdiff1d(objids, objids_known, assume_unique=True)
        objids_tot = union1d(objids, objids_known)

        # Assign all objids to the proper bins
        objid_bins = assign_objids(objids)

        # Loop over all bins in objid_bins and prepare their files
        for (left, right), objids_bin in objid_bins.items():
            # Determine the file this bin belongs to
            objid_file = path.join(args.mld, OBJS_FILE.format(left, right))

            # Open the objid HDF5-file, creating it if it does not exist yet
            with h5py.File(objid_file, mode='a') as obj_file:
                # Create external link between this file and master file
                group_name = f"{OBJID_NAME}-{OBJID_NAME}".format(left, right)
                if group_name not in m_file:
                    m_file[group_name] = h5py.ExternalLink(
                        path.basename(obj_file.filename), '/')

                # Loop over all objids
                for objid in objids_bin:
                    # Create a group for every objid in obj_file
                    obj_file.create_group(OBJID_NAME.format(objid))

        # Save which objids the database knows about now
        objids_dset = m_file.require_dataset('objids',
                                             shape=(n_objids_known,),
                                             dtype=int,
                                             maxshape=(None,))
        objids_dset.resize(objids_tot.size, axis=0)
        objids_dset[n_objids_known:] = objids

        # Obtain what exposures the database knows about
        expnums_known = m_file.get('expnums', np.array([], dtype=int))
        n_expnums_known = len(expnums_known)

    # Obtain sorted string of all files available
    filenames = str(sorted(next(os.walk(args.dir))[2]))

    # Create a regex iterator
    re_iter = re.finditer(EXP_REGEX, filenames)

    # Create dict with all exposure files except those that are known
    # TODO: Maybe save the last-modified date of every exposure and compare it
    exp_dict = {int(m['expnum']): (m['exp_file'], m['xtr_file'])
                for m in re_iter if int(m['expnum']) not in expnums_known}

    # Process all exposure files
    for expnum, exp_files in exp_dict.items():
        process_exp_files(expnum, exp_files, args)


# %% FUNCTION DEFINITIONS
# This function determines which objid belongs to which objid interval/bin
def assign_objids(objids):
    """
    Determines which bins/intervals the object ids in `objids` belong to and
    returns their assignments in a dict.

    Parameters
    ----------
    objids : 1D :obj:`~numpy.ndarray` object of int
        Array of object ID integers.

    Returns
    -------
    objid_bins : dict
        Dict containing what bin/interval should contain which object IDs.

    """

    # Obtain the indices of the bins every objid belongs to
    bin_idx = objids//N_OBJIDS

    # Assign all objids to the correct bins
    def func(i): return(i*N_OBJIDS, (i+1)*N_OBJIDS-1)
    objid_bins = {func(i): objids[bin_idx == i] for i in set(bin_idx)}

    # Return objid_bins
    return(objid_bins)


# This function processes an exposure file
def process_exp_files(expnum, exp_files, args):
    print(expnum, exp_files)


# %% MAIN FUNCTION
def main():
    """

    """

    # Initialize argparser
    parser = argparse.ArgumentParser(
        'mld',
        description=PKG_NAME,
        formatter_class=HelpFormatterWithSubCommands,
        add_help=True,
        allow_abbrev=True)

    # Add subparsers
    subparsers = parser.add_subparsers(
        title='commands',
        metavar='COMMAND')

    # OPTIONAL ARGUMENTS
    # Add version argument
    parser.add_argument(
        '-v', '--version',
        action='version',
        version="%s v%s" % (PKG_NAME, __version__))

    # Add dir argument
    parser.add_argument(
        '-d', '--dir',
        help="Micro-lensing database directory to use",
        metavar='DIR',
        action='store',
        default=path.abspath('.'),
        type=str,
        dest='dir')

    # INIT COMMAND
    # Add init subparser
    init_parser = subparsers.add_parser(
        'init',
        description="Initialize a new micro-lensing database in DIR",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=True)

    # Set defaults for init_parser
    init_parser.set_defaults(func=init)

    # UPDATE COMMAND
    # Add update subparser
    update_parser = subparsers.add_parser(
        'update',
        description="Update an existing micro-lensing database in DIR",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=True)

    # Set defaults for update_parser
    update_parser.set_defaults(func=update)

    # Parse the arguments
    args = parser.parse_args()

    # Make sure provided dir is an absolute path
    args.dir = path.abspath(args.dir)

    # Check if provided dir exists
    if not path.exists(args.dir):
        # If not, raise error and exit
        print("ERROR: Provided DIR %r does not exist!" % (args.dir))
        sys.exit()

    # Obtain absolute path to database
    args.mld = path.join(args.dir, MLD_NAME)

    # If arguments is empty (no func was provided), show help
    if 'func' not in args:
        parser.print_help()
    # Else, call the corresponding function
    else:
        args.func(args)


# %% MAIN EXECUTION
if(__name__ == '__main__'):
    main()
