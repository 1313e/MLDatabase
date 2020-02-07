# -*- coding: utf-8 -*-

# %% IMPORTS
# TODO: Use 'argcomplete'?
# Built-in imports
import argparse
import os
from os import path
import re
import shutil
import sys
from textwrap import dedent
import time

# Package imports
import h5py
import numpy as np
import pandas as pd
from tqdm import tqdm
import vaex

# MLDatabase imports
from mldatabase import (
    __version__, EXP_HEADER, EXP_REGEX, MASTER_EXP_FILE, MASTER_FILE, MLD_NAME,
    PKG_NAME, REQ_FILES, SIZE_SUFFIXES, XTR_HEADER)

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
    check_database_exist(False, args)

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


# This function handles the 'query' subcommand
def query(args):
    # Check if a database already exists in this folder
    check_database_exist(True, args)


# This function handles the 'reset' subcommand
def reset(args):
    # Check if a database already exists in this folder
    check_database_exist(True, args)

    # Delete the entire database
    shutil.rmtree(args.mld)

    # Initialize the database
    init(args)


# This function handles the 'status' subcommand
def status(args):
    # Check if a database already exists in this folder
    exists = path.exists(args.mld)

    # Initialize empty list of statistics and empty string list
    stat_list = []
    str_list = []

    # Add paths to stat_list
    stat_list.append(('Paths',))
    stat_list.append(('DIR', args.dir))
    stat_list.append(('MLDatabase', args.mld if exists else 'N/A'))

    # If the database exists, gather more statistics
    if exists:
        # Add category
        stat_list.append(('Database',))

        # Obtain database size
        mld_size = path.getsize(args.master_exp_file)
        size_order = int(np.log2(mld_size)//10) if mld_size else 0
        size_val = mld_size/(1 << (size_order*10))
        size_suffix = SIZE_SUFFIXES[size_order]
        stat_list.append(('Size', f"{size_val:,.1f} {size_suffix}"))

        # Add 'last updated' stat
        mtime = time.localtime(path.getmtime(args.master_exp_file))
        stat_list.append(('Last updated',
                          time.strftime('%a %d %b %Y %H:%M:%S %Z', mtime)))

        # Open the master hdf5-file
        with h5py.File(args.master_file, 'r') as m_file:
            # Obtain relevant statistics
            stat_list.append(('# of exposures', m_file.attrs['n_expnums']))
            stat_list.append(('# of known objects', m_file.attrs['n_objids']))

    # Determine the maximum length of all keys
    width = max([len(stat[0]) for stat in stat_list if (len(stat) == 2)])

    # Add header
    str_list.append("DATABASE STATUS")
    str_list.append('='*width)

    # Process all gathered statistics
    for stat in stat_list:
        # If stat has a single argument, it is a category
        if(len(stat) == 1):
            str_list.append("")
            str_list.append(f"{stat[0]}")
            str_list.append('-'*width)

        # Else, it has two values
        else:
            # Extract both values
            key, value = stat

            # Print proper
            if isinstance(value, (int, float, np.integer, np.floating)):
                str_list.append(f"{key: <{width}}\t{value:,}")
            else:
                str_list.append(f"{key: <{width}}\t{value}")

    # Add final dividing line
    str_list.append('='*width)

    # Combine all strings in str_list together
    status_str = '\n'.join(str_list)

    # Print it
    print(status_str)


# This function handles the 'update' subcommand
def update(args):
    # Check if a database already exists in this folder
    check_database_exist(True, args)
    print(f"Updating micro-lensing database in {args.dir!r}.")

#    # Obtain path to reference exposure file
#    ref_exp_file = path.join(args.dir, 'Exp0.csv')

#    # Read in the first column of this file (which should be all objids)
#    objids = pd.read_csv(ref_exp_file, skipinitialspace=True, header=None,
#                         names=EXP_HEADER, usecols=['objid'], squeeze=True,
#                         dtype=EXP_HEADER, nrows=10000)
#
#    # If objids contains no elements, raise error and exit
#    if objids.empty:
#        print(f"ERROR: Reference exposure file {ref_exp_file!r} contains no "
#              f"objects!")
#        sys.exit()

    # Open the master HDF5-file, creating it if it does not exist yet
    with h5py.File(args.master_file, mode='a') as m_file:
        # Set the version of MLDatabase
        mld_version = m_file.attrs.setdefault('version', __version__)

        # Obtain what exposures the database knows about
        n_expnums_known = m_file.attrs.setdefault('n_expnums', 0)
        expnums_dset =\
            m_file.require_dataset('expnums',
                                   shape=(n_expnums_known,),
                                   dtype=[*list(XTR_HEADER.items())[:-1],
                                          ('last_modified', int)],
                                   maxshape=(None,))
        expnums_known = expnums_dset[:]

    # Obtain sorted string of all files available
    filenames = str(sorted(next(os.walk(args.dir))[2])[:10])

    # Create a regex iterator
    re_iter = re.finditer(EXP_REGEX, filenames)

    # Create dict with all exposure files
    exp_dict = {int(m['expnum']): (path.join(args.dir, m['exp_file']),
                                   path.join(args.dir, m['xtr_file']))
                for m in re_iter}

    # Add the required flat exposure files (REGEX above explicitly ignores it)
#    exp_dict[0] = (path.join(args.dir, REQ_FILES[0]),
#                   path.join(args.dir, REQ_FILES[1]))

    # Initialize the number of exposures found and their types
    n_expnums = len(exp_dict)
    expnums_outdated = []

    # Determine which ones require updating
    for expnum, *_, mtime in expnums_known:
        # Try to obtain the exp_files of this expnum
        exp_files = exp_dict.get(expnum)

        # If this is not None, it is already known
        if exp_files is not None:
            # Check if it requires updating by comparing last-modified times
            if(path.getmtime(exp_files[0]) > mtime):
                # If so, add to expnums_outdated
                expnums_outdated.append(expnum)
            else:
                # If not, remove from dict
                exp_dict.pop(expnum)

    # Print the number of exposure files found
    n_expnums_outdated = len(expnums_outdated)
    n_expnums_new = len(exp_dict)-n_expnums_outdated
    print(f"Found {n_expnums:,} exposure files, of which {n_expnums_new:,} are"
          f" new and {n_expnums_outdated:,} are outdated.")

    # If exp_dict contains at least 1 item
    if exp_dict:
        # Create tqdm iterator for processing
        exp_iter = tqdm(exp_dict.items(), desc="Processing exposure files",
                        dynamic_ncols=True)

        # Create empty list of temporary HDF5-files
        temp_files = []

        # Open master file
        with h5py.File(args.master_file, 'r+') as m_file:
            # Process all exposure files
            try:
                for expnum, exp_files in exp_iter:
                    # Set which exposure is being processed in exp_iter
                    exp_iter.set_postfix_str(path.basename(exp_files[0]))

                    # Process this exposure
                    temp_files.append(
                        process_exp_files(m_file, expnum, exp_files, args))

            # If a KeyboardInterrupt is raised, update database with progress
            except KeyboardInterrupt:
                print("WARNING: Processing has been interrupted. Updating "
                      "database with currently processed exposures.")

            # Obtain the total number of exposures now
            n_expnums_known = m_file.attrs['n_expnums']

        # Update database
        print("Updating database with processed exposures.")

        # Open all temporary exposure HDF5-files
        temp_df = vaex.open_many(temp_files)

        # If the master exposure file already exists, open it
        if path.exists(args.master_exp_file):
            # Add master_exp_file to temp_files
            temp_files.insert(0, args.master_exp_file)

            # Open the master exposure file
            master_df = vaex.open(args.master_exp_file)

            # Solely select the exposures that were not outdated
            for expnum in expnums_outdated:
                master_df = master_df.filter(master_df.expnum != expnum, 'and')

            # Extract the master DataFrame
            master_df = master_df.extract()

            # Concatenate the two DataFrames
            master_df = master_df.concat(temp_df)

        # If not, master_df is equal to temp_df
        else:
            master_df = temp_df

        # Export to HDF5
        master_temp_file = path.join(args.mld, 'temp.hdf5')
        master_df.export_hdf5(master_temp_file)

        # Determine all objids that are known
        print("Determining all objects in the database.")
        objids, counts = np.unique(master_df['objid'].values,
                                   return_counts=True)

        # Close all temporary HDF5-files
        master_df.close_files()

        # Remove all temporary files
        for temp_file in temp_files:
            os.remove(temp_file)

        # Rename master_temp_file to master exposure file name
        os.rename(master_temp_file, args.master_exp_file)

        # Open master file
        with h5py.File(args.master_file, 'r+') as m_file:
            # Obtain previously known objids
            n_objids_known = m_file.attrs.setdefault('n_objids', 0)
            objids_dset = m_file.require_dataset('objids',
                                                 shape=(n_objids_known,),
                                                 dtype=[('objid', int),
                                                        ('count', int)],
                                                 maxshape=(None,))

            # Save currently known objids
            n_objids = len(objids)
            objids_dset.resize(n_objids, axis=0)
            objids_dset['objid'] = objids
            objids_dset['count'] = counts
            m_file.attrs['n_objids'] = n_objids

            # Obtain the total number of exposures now
            n_expnums = m_file.attrs['n_expnums']

        # Print that processing is finished
        print(f"The database now contains {n_expnums:,} exposures with "
              f"{n_objids:,} objects.")

    # If no new exposure files are found, database is already up-to-date
    else:
        print("Database is already up-to-date.")


# %% FUNCTION DEFINITIONS
# This function processes an exposure file
def process_exp_files(m_file, expnum, exp_files, args):
    # Unpack exp_files
    exp_file, xtr_file = exp_files

    # Read in the exp_file
    exp_data = vaex.from_csv(exp_file, skipinitialspace=True, header=None,
                             names=EXP_HEADER, squeeze=True, dtype=EXP_HEADER,
                             copy_index=False)

    # Read in the xtr_file
    xtr_data = pd.read_csv(xtr_file, skipinitialspace=True, header=None,
                           names=XTR_HEADER, squeeze=True, dtype=XTR_HEADER,
                           usecols=range(len(XTR_HEADER)-1))
    xtr_data = xtr_data.to_numpy()[0]

    # Check if the 'expnum' column contains solely expnum
    if not (exp_data['expnum'] == expnum).evaluate().all():
        # If not, raise error and exit
        # TODO: Should it simply be skipped instead?
        print(f"ERROR: Exposure file {exp_file!r} contains multiple "
              f"exposures!")
        sys.exit()

    # Export vaex DataFrame to HDF5
    exp_file_hdf5 = path.join(args.mld, f'exp{expnum}.hdf5')
    exp_data.export_hdf5(exp_file_hdf5)

    # Check if this exposure has been processed before
    expnums = m_file['expnums']['expnum']
    expnums = expnums if expnums.size else expnums['expnum']
    index = np.nonzero(expnums == expnum)[0]

    # Save that this exposure has been processed
    if index.size:
        m_file['expnums'][index[0]] = (*xtr_data, path.getmtime(exp_file))
    else:
        m_file['expnums'].resize(m_file.attrs['n_expnums']+1, axis=0)
        m_file['expnums'][-1] = (*xtr_data, path.getmtime(exp_file))
        m_file.attrs['n_expnums'] += 1

    # Return exp_file_hdf5
    return(exp_file_hdf5)


# This function checks if the database exists and proceeds accordingly
def check_database_exist(req, args):
    # Check if the database exists
    exists = path.exists(args.mld)

    # If exists and req are equal, return
    if req is exists:
        return

    # Else, raise the proper error
    else:
        # If database exists
        if exists:
            print(f"ERROR: Provided DIR {args.dir!r} already contains a "
                  f"micro-lensing database!")
            sys.exit()
        # If database does not exist
        else:
            print(f"ERROR: Provided DIR {args.dir!r} does not contain a "
                  f"micro-lensing database!")
            sys.exit()


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

    # QUERY COMMAND
    # Add query subparser
    query_parser = subparsers.add_parser(
        'query',
        description="Query an existing micro-lensing database in DIR",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=True)

    # Set defaults for query_parser
    query_parser.set_defaults(func=query)

    # RESET COMMAND
    # Add reset subparser
    reset_parser = subparsers.add_parser(
        'reset',
        description=("Delete and reinitialize an existing micro-lensing "
                     "database in DIR"),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=True)

    # Set defaults for reset_parser
    reset_parser.set_defaults(func=reset)

    # SEARCH COMMAND
    # Add search subparser
    search_parser = subparsers.add_parser(
        'search',
        description="Alias for 'query'",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=True)

    # Set defaults for search_parser
    search_parser.set_defaults(func=query)

    # STATUS COMMAND
    # Add status subparser
    status_parser = subparsers.add_parser(
        'status',
        description="Show the status of the micro-lensing database in DIR",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=True)

    # Set defaults for status_parser
    status_parser.set_defaults(func=status)

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
    args.master_file = path.join(args.mld, MASTER_FILE)
    args.master_exp_file = path.join(args.mld, MASTER_EXP_FILE)

    # If arguments is empty (no func was provided), show help
    if 'func' not in args:
        parser.print_help()
    # Else, call the corresponding function
    else:
        args.func(args)


# %% MAIN EXECUTION
if(__name__ == '__main__'):
    main()
