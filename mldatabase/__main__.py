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
from tqdm import tqdm

# MLDatabase imports
from mldatabase import (
    __version__, EXP_HEADER, EXP_REGEX, MASTER_FILE,
    MLD_NAME, N_OBJIDS, OBJID_NAME, OBJS_BIN, OBJS_FILE, PKG_NAME, REQ_FILES)

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
        print(f"ERROR: Provided DIR {args.dir!r} already contains a "
              f"micro-lensing database!")
        sys.exit()

    # Check if these files are present
    for req_file in REQ_FILES:
        if not path.exists(path.join(args.dir, req_file)):
            # If not, raise error and exit
            print(f"ERROR: Provided DIR {args.dir!r} does not contain required"
                  f" files for micro-lensing database!")
            sys.exit()

    # Make the database directory
    print(f"Initializing micro-lensing database in {args.dir!r}.")
    os.mkdir(args.mld)

    # Update the database
    update(args)


# This function handles the 'update' subcommand
def update(args):
    # Check if a database already exists in this folder
    if not path.exists(args.mld):
        # If not, raise error and exit
        print(f"ERROR: Provided DIR {args.dir!r} does not contain a "
              f"micro-lensing database!")
        sys.exit()
    print(f"Updating micro-lensing database in {args.dir!r}.")

#    # TODO: This does not belong here and must be removed later
#    # Obtain sorted string of all files available
#    filenames = str(sorted(next(os.walk(args.dir))[2])[:10])
#
#    # Create a regex iterator
#    re_iter = re.finditer(EXP_REGEX, filenames)
#
#    # Create dict with all exposure files
#    exp_dict = {int(m['expnum']): (path.join(args.dir, m['exp_file']),
#                                   path.join(args.dir, m['xtr_file']))
#                for m in re_iter}
#
#    # TODO: Remove this later
#    key = list(exp_dict.keys())[0]
#    exp_dict = {key: exp_dict[key]}
#
#    # Obtain path to reference exposure file
#    ref_exp_file = path.join(args.dir, exp_dict[key][0])

    # Obtain path to reference exposure file
    ref_exp_file = path.join(args.dir, 'Exp0.csv')

    # Read in the first column of this file (which should be all objids)
    objids = pd.read_csv(ref_exp_file, skipinitialspace=True, header=None,
                         names=EXP_HEADER, usecols=['objid'], squeeze=True,
                         dtype=EXP_HEADER)

    # If objids contains no elements, raise error and exit
    if objids.empty:
        print(f"ERROR: Reference exposure file {ref_exp_file!r} contains no "
              f"objects!")
        sys.exit()

    # Convert objids to NumPy array
    objids = objids.to_numpy()
    n_objids = len(objids)

    # Open the master HDF5-file, creating it if it does not exist yet
    args.master_file = path.join(args.mld, MASTER_FILE)
    with h5py.File(args.master_file, mode='a') as m_file:
        # Obtain the known objids
        n_objids_known = m_file.attrs.setdefault('n_objids', 0)
        objids_dset = m_file.require_dataset('objids',
                                             shape=(n_objids_known,),
                                             dtype=int,
                                             maxshape=(None,))
        objids_known = objids_dset[:]

        # Take the difference and union between objids and the known ones
        objids = setdiff1d(objids, objids_known, assume_unique=True)
        objids_tot = union1d(objids, objids_known)
        print(f"Found {n_objids:,} objects, of which {objids.size:,} are new.")

        # Assign all objids to the proper bins
        objid_bins = assign_objids(objids)

        # Loop over all bins in objid_bins and prepare their files
        bin_iter = tqdm(objid_bins.items(), dynamic_ncols=True,
                        desc="Creating datasets for new objects")
        for (left, right), objids_bin in bin_iter:
            # Determine the file this bin belongs to
            objid_file = path.join(args.mld, OBJS_FILE.format(left, right))

            # Open the objid HDF5-file, creating it if it does not exist yet
            with h5py.File(objid_file, mode='a') as obj_file:
                # Create external link between this file and master file
                group_name = OBJS_BIN.format(left, right)
                if group_name not in m_file:
                    m_file[group_name] = h5py.ExternalLink(
                        path.basename(obj_file.filename), '/')

                # Loop over all objids
                for objid in objids_bin:
                    # Create a dataset for every objid in obj_file
                    obj_file.create_dataset(OBJID_NAME.format(objid),
                                            shape=(0,),
                                            dtype=list(EXP_HEADER.items())[1:],
                                            maxshape=(None,))

        # Save which objids the database knows about now
        objids_dset.resize(objids_tot.size, axis=0)
        objids_dset[n_objids_known:] = objids
        m_file.attrs['n_objids'] = objids_tot.size
        print(f"The database now contains {objids_tot.size:,} objects.")

        # Obtain what exposures the database knows about
        n_expnums_known = m_file.attrs.setdefault('n_expnums', 0)
        expnums_dset = m_file.require_dataset('expnums',
                                              shape=(n_expnums_known, 2),
                                              dtype=int,
                                              maxshape=(None, 2))
        expnums_known = expnums_dset[:]

    # Obtain sorted string of all files available
    filenames = str(sorted(next(os.walk(args.dir))[2]))

    # Create a regex iterator
    re_iter = re.finditer(EXP_REGEX, filenames)

    # Create dict with all exposure files
    exp_dict = {int(m['expnum']): (path.join(args.dir, m['exp_file']),
                                   path.join(args.dir, m['xtr_file']))
                for m in re_iter}

    # Initialize the number of exposures found and their types
    n_expnums = len(exp_dict)
    n_expnums_outdated = 0

    # Determine which ones require updating
    for expnum, mtime in expnums_known:
        # Try to obtain the exp_files of this expnum
        exp_files = exp_dict.get(expnum)

        # If this is not None, it is already known
        if exp_files is not None:
            # Check if it requires updating by comparing last-modified times
            if(path.getmtime(exp_files[0]) > mtime):
                # If so, increase n_expnums_outdated by 1
                n_expnums_outdated += 1
            else:
                # If not, remove from dict
                exp_dict.pop(expnum)

    # Print the number of exposure files found
    n_expnums_new = len(exp_dict)-n_expnums_outdated
    print(f"Found {n_expnums:,} exposure files, of which {n_expnums_new:,} are"
          f" new and {n_expnums_outdated:,} are outdated.")

    # Create tqdm iterator for processing
    exp_iter = tqdm(exp_dict.items(), desc="Processing exposure files",
                    dynamic_ncols=True)

    # Process all exposure files
    with h5py.File(args.master_file, 'r+') as m_file:
        for expnum, exp_files in exp_iter:
            process_exp_files(m_file, expnum, exp_files, args)

        # Print that processing is finished
        print(f"The database now contains {m_file.attrs['n_expnums']} "
              f"exposures.")


# %% FUNCTION DEFINITIONS
# This function returns the dataset belonging to a specified objid
def get_objid_dataset(m_file, objid):
    """
    Returns the :obj:`~h5py.Dataset` object in `m_file` that the provided
    `objid` belongs to.

    Parameters
    ----------
    m_file : :obj:`~h5py.File` object
        An open database master file.
    objid : int
        The identifier of the requested object.

    Returns
    -------
    objid_dset : :obj:`~h5py.Dataset`
        The dataset corresponding to `objid`.

    """

    # Obtain the bin_idx
    bin_idx = objid//N_OBJIDS

    # Determine the bin name
    bin_name = OBJS_BIN.format(bin_idx*N_OBJIDS, (bin_idx+1)*N_OBJIDS-1)

    # Determine the objid name
    objid_name = OBJID_NAME.format(objid)

    # Return corresponding dataset
    return(m_file[f"{bin_name}/{objid_name}"])


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
def process_exp_files(m_file, expnum, exp_files, args):
    # Unpack exp_files
    exp_file, xtr_file = exp_files

    # Read in the exp_file
    exp_data = pd.read_csv(exp_file, skipinitialspace=True, header=None,
                           names=EXP_HEADER, index_col='objid', squeeze=True,
                           dtype=EXP_HEADER)

    # Check if the 'expnum' column contains solely expnum
    if not (exp_data['expnum'] == expnum).all():
        # If not, raise error and exit
        # TODO: Should it simply be skipped instead?
        print(f"ERROR: Exposure file {exp_file!r} contains multiple "
              f"exposures!")
        sys.exit()

    # Convert the entire DataFrame to a NumPy array
    objids = list(exp_data.index)
    exp_data = exp_data.to_records(index=False)

    # Loop over all observations/detections in this exposure
    data_iter = tqdm(zip(objids, exp_data), total=len(objids),
                     desc=f"Processing {path.basename(exp_file)}",
                     dynamic_ncols=True, position=1, leave=None)
    for objid, obs_data in data_iter:
        # Obtain the dataset of this objid
        objid_dset = get_objid_dataset(m_file, objid)

        # Increase its size by 1
        objid_dset.resize(objid_dset.size+1, axis=0)

        # Assign all values
        objid_dset[-1] = obs_data

    # Save that this exposure has been processed
    m_file['expnums'].resize(m_file.attrs['n_expnums']+1, axis=0)
    m_file['expnums'][-1] = (expnum, path.getmtime(exp_file))
    m_file.attrs['n_expnums'] += 1


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
        version=f"{PKG_NAME} v{__version__}")

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
        print(f"ERROR: Provided DIR {args.dir!r} does not exist!")
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
