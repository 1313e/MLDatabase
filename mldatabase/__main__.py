# -*- coding: utf-8 -*-

# %% IMPORTS
# TODO: Use 'argcomplete'?
# Built-in imports
import argparse
from contextlib import contextmanager
from glob import glob
from itertools import islice
import os
from os import path
from pkg_resources import parse_version
import re
import shutil
import sys
from tempfile import NamedTemporaryFile
import time

# Package imports
import IPython
import h5py
import numpy as np
import pandas as pd
from sortedcontainers import SortedDict as sdict
from tqdm import tqdm

# MLDatabase imports
from mldatabase import __version__
from mldatabase._globals import (
    EXP_HEADER, EXP_REGEX, MASTER_EXP_FILE, MASTER_FILE, MLD_NAME, PKG_NAME,
    REQ_FILES, SIZE_SUFFIXES, TEMP_EXP_FILE, XTR_HEADER)

# All declaration
__all__ = ['open_database']


# %% GLOBALS
# Define main description of this package
main_desc = (f"{PKG_NAME}; a Python CLI package for making micro-lensing "
             f"databases from DECam exposures.")

# Define global ARGS
global ARGS
ARGS = argparse.Namespace()


# %% CLASS DEFINITIONS
# Define formatter that automatically extracts help strings of subcommands
class HelpFormatterWithSubCommands(argparse.ArgumentDefaultsHelpFormatter):
    # Override the add_argument function
    def add_argument(self, action):
        # Check if the help of this action is required
        if action.help is not argparse.SUPPRESS:
            # Check if this action is a subparser's action
            if isinstance(action, argparse._SubParsersAction):
                # Convert action.choices to a sorted dictionary
                choices = sdict(action.choices)

                # If so, loop over all subcommands defined in the action
                for name, subparser in choices.items():
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
def cli_init():
    # Check if a database already exists in this folder
    check_database_exists(False)

    # Check if these files are present
    for req_file in REQ_FILES:
        if not path.exists(path.join(ARGS.dir, req_file)):
            # If not, raise error and exit
            raise_error(f"Provided DIR {ARGS.dir!r} does not contain required"
                        f" files for micro-lensing database!")

    # Make the database directory
    print(f"Initializing micro-lensing database in {ARGS.dir!r}.")
    os.mkdir(ARGS.mld)

    # Update the database
    cli_update()


# This function handles the 'ipython' subcommand
def cli_ipython():
    # Open the database
    with open_database() as df:
        # Embed an IPython console
        IPython.embed(
            banner1=("Starting IPython session. Database is available as 'df',"
                     " a vaex DataFrame.\n"
                     "See https://vaex.readthedocs.io/en/latest/tutorial.html "
                     "for how to interact with vaex DataFrames.\n"),
            exit_msg="Leaving IPython session. Database will be closed.",
            colors='Neutral',
            user_ns={'df': df})


# This function handles the 'reset' subcommand
def cli_reset():
    # Check if a database already exists in this folder
    check_database_exists(True)

    # Determine all files in the database directory as a string
    mld_files_str = str(next(os.walk(ARGS.mld))[2])

    # If the database exists, make sure currently no lock files exist
    if '.lock' in mld_files_str:
        # If a lock-file already exists, raise error and exit
        raise_error(f"Database in provided DIR {ARGS.dir!r} is currently "
                    f"being used! Reset is not possible!")

    # Delete the entire database
    shutil.rmtree(ARGS.mld)

    # Initialize the database
    cli_init()


# This function handles the 'status' subcommand
def cli_status():
    # Check if a database already exists in this folder
    exists = path.exists(ARGS.mld)

    # Initialize empty list of statistics and empty string list
    stat_list = []
    str_list = []

    # Add paths to stat_list
    stat_list.append(('Paths',))
    stat_list.append(('DIR', ARGS.dir))
    stat_list.append(('MLDatabase', ARGS.mld if exists else 'N/A'))

    # If the database exists, gather more statistics
    if exists:
        # Add category
        stat_list.append(('Database',))

        # Obtain database size
        mld_size = path.getsize(ARGS.master_exp_file)
        size_order = int(np.log2(mld_size)//10) if mld_size else 0
        size_val = mld_size/(1 << (size_order*10))
        size_suffix = SIZE_SUFFIXES[size_order]
        stat_list.append(('Size', f"{size_val:,.1f} {size_suffix}"))

        # Add 'last updated' stat
        mtime = time.localtime(path.getmtime(ARGS.master_exp_file))
        stat_list.append(('Last updated',
                          time.strftime('%a %d %b %Y %H:%M:%S %Z', mtime)))

        # Open the master hdf5-file
        with h5py.File(ARGS.master_file, 'r') as m_file:
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

            # Print value with proper formatting
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
def cli_update():
    # Check if a database already exists in this folder
    check_database_exists(True)

    # Determine path to update-lock file
    lock_file = path.join(ARGS.mld, '.mld_update.lock')

    # Determine all files in the database directory as a string
    mld_files_str = str(next(os.walk(ARGS.mld))[2])

    # If the database exists, make sure currently no lock files exist
    if '.lock' in mld_files_str:
        # If a lock-file already exists, raise proper error
        if '.mld_update.lock' in mld_files_str:
            raise_error(f"Database in provided DIR {ARGS.dir!r} is currently "
                        f"already being updated by a different process! Update"
                        f" is not possible!")
        else:
            raise_error(f"Database in provided DIR {ARGS.dir!r} is currently "
                        f"being accessed! Update is not possible!")

    # Create the lock-file
    os.mknod(lock_file)

    # Wrap in try-statement to ensure lock-file is removed afterward
    try:
        # Perform the update
        perform_update()

    # Remove lock-file
    finally:
        os.remove(lock_file)


# %% FUNCTION DEFINITIONS
# This function returns a context manager used for opening and closing database
@contextmanager
def open_database(exp_dir=None):
    """
    Context manager for accessing an existing micro-lensing database in the
    provided `exp_dir` as a :obj:`~vaex.dataframe.DataFrame` object.

    See https://vaex.readthedocs.io/en/latest/tutorial.html for how to interact
    with vaex DataFrames.

    Optional
    --------
    exp_dir : str or None. Default: None
        The relative or absolute path to the directory that contains an
        existing micro-lensing database.
        If *None*, the current working directory is used.
        This argument is equivalent to the optional `-d`/`--dir` argument when
        using the command-line interface.

    Yields
    ------
    df : :obj:`~vaex.dataframe.DataFrame` object
        The vaex DataFrame that contains all of the data stored in the database
        in `exp_dir`.

    """

    # Check if ARGS is available
    try:
        mld = ARGS.mld
        exp_dir = ARGS.dir

    # If it is not, obtain the mld directory manually
    except AttributeError:
        # Determine directory path
        ARGS.dir = path.abspath(exp_dir if exp_dir else '.')

        # Check if provided dir exists
        if not path.exists(ARGS.dir):
            # If not, raise error
            raise OSError(f"Provided DIR {ARGS.dir!r} does not exist!")

        # Obtain absolute path to database
        ARGS.mld = path.join(ARGS.dir, MLD_NAME)
        ARGS.master_file = path.join(ARGS.mld, MASTER_FILE)
        ARGS.master_exp_file = path.join(ARGS.mld, MASTER_EXP_FILE)

        # Set CLI_flag to False
        ARGS.CLI_flag = False

        # Obtain mld and exp_dir
        mld = ARGS.mld
        exp_dir = ARGS.dir

    # Check that database file exists
    check_database_exists(True)

    # If so, make sure that the update-lock file does not exist
    if path.exists(path.join(mld, '.mld_update.lock')):
        # If the update-lock file does exist, raise error and exit
        raise_error(f"Database in provided DIR {exp_dir!r} is currently "
                    f"being updated! Access is not possible!")

    # Obtain list of non-merged exposures
    temp_files = glob(path.join(mld, TEMP_EXP_FILE.replace('{}', '*')))

    # If temp_files is not empty, raise warning
    if temp_files:
        print(f"WARNING: Database in provided DIR {exp_dir!r} was interrupted "
              f"during last update. It can be accessed, but it is recommended "
              f"to finish the update with 'mld update -n 0' first!")

    # Obtain the path to the master exposure file
    master_exp_file = path.join(mld, MASTER_EXP_FILE)

    # Import vaex
    import vaex

    # Open a lock-file
    with NamedTemporaryFile(suffix='.lock', prefix='.mld_access_', dir=mld):
        # Wrap within try-finally statement
        try:
            # Open the database
            df = vaex.open(master_exp_file)

            # Yield the database
            yield df

        # After context manager returns, clean up
        finally:
            # Close database
            df.close()


# This function performs the update process
def perform_update():
    # Print that database is being updated
    print(f"Updating micro-lensing database in {ARGS.dir!r}.")

    # Open the master HDF5-file, creating it if it does not exist yet
    with h5py.File(ARGS.master_file, mode='a') as m_file:
        # Set the version of MLDatabase
        m_file.attrs['version'] = __version__

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
    filenames = str(sorted(next(os.walk(ARGS.dir))[2]))

    # Create a regex iterator
    re_iter = re.finditer(EXP_REGEX, filenames)

    # Create dict with up to ARGS.n_expnums exposure files
    exp_dict = {int(m['expnum']): (path.join(ARGS.dir, m['exp_file']),
                                   path.join(ARGS.dir, m['xtr_file']))
                for m in islice(re_iter, ARGS.n_expnums)}

    # Add the required flat exposure files (REGEX above explicitly ignores it)
#    exp_dict[0] = (path.join(ARGS.dir, REQ_FILES[0]),
#                   path.join(ARGS.dir, REQ_FILES[1]))

    # Initialize the number of exposures found and their types
    n_expnums = len(exp_dict)
    expnums_outdated = []

    # Create empty list of temporary HDF5-files
    temp_files = []

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
                continue
            else:
                # If not, remove from dict
                exp_dict.pop(expnum)

        # Determine path to temporary HDF5-file of exposure
        temp_hdf5 = path.join(ARGS.mld, TEMP_EXP_FILE.format(expnum))

        # If it already exists, add it to temp_files
        if path.exists(temp_hdf5):
            temp_files.append(temp_hdf5)

    # Print the number of exposure files found
    n_expnums_outdated = len(expnums_outdated)
    n_expnums_new = len(exp_dict)-n_expnums_outdated
    n_expnums_temp = len(temp_files)
    print(f"\nFound {n_expnums:,} exposure files, of which {n_expnums_new:,} "
          f"are new and {n_expnums_outdated:,} are outdated. Also found "
          f"{n_expnums_temp:,} processed exposure files that require merging.")

    # If exp_dict contains at least 1 item
    if exp_dict:
        # Create tqdm iterator for processing
        exp_iter = tqdm(exp_dict.items(), desc="Processing exposure files",
                        dynamic_ncols=True)

        # Process all exposure files
        try:
            for expnum, exp_files in exp_iter:
                # Set which exposure is being processed in exp_iter
                exp_iter.set_postfix_str(path.basename(exp_files[0]))

                # Process this exposure
                temp_files.append(process_exp_files(expnum, exp_files))

        # If a KeyboardInterrupt is raised, update database with progress
        except KeyboardInterrupt:
            print("WARNING: Processing has been interrupted. Updating "
                  "database with currently processed exposures.")

        # Open master file
        with h5py.File(ARGS.master_file, 'r+') as m_file:
            # Obtain the total number of exposures now
            n_expnums_known = m_file.attrs['n_expnums']

    # If temp_files contains at least 1 item
    if temp_files:
        # Import vaex
        import vaex

        # Update database
        print("\nUpdating database with processed exposures (NOTE: This may "
              "take a while for large databases).")

        # Divide temp_files up into lists of length 100 with last of length 150
        n_temp = len(temp_files)
        temp_files = [temp_files[slc] for slc in dyn_range(len(temp_files))]

        # If the master exposure file exists and there are outdated exposures
        if path.exists(ARGS.master_exp_file) and expnums_outdated:
            # Wrap in try-statement to ensure file is closed
            try:
                # Open the master exposure file
                master_df = vaex.open(ARGS.master_exp_file)

                # Solely select the exposures that were not outdated
                for expnum in expnums_outdated:
                    master_df = master_df.filter(master_df.expnum != expnum,
                                                 'and')

                # Extract the master DataFrame
                master_df = master_df.extract()

                # Export to HDF5
                master_temp_file = path.join(ARGS.mld, 'temp.hdf5')
                master_df.export_hdf5(master_temp_file)

            # Close master exposure file
            finally:
                master_df.close()

            # Remove original master file
            os.remove(ARGS.master_exp_file)

            # Rename master_temp_file to master exposure file name
            os.rename(master_temp_file, ARGS.master_exp_file)

        # Create tqdm iterator for merging
        temp_iter = tqdm(desc="Merging processed exposure files", total=n_temp,
                         dynamic_ncols=True)

        # Loop over all temporary exposure HDF5-files
        # TODO: Figure out how to avoid copying over all the data every time
        for temp_files_list in temp_files:
            # Determine number of files in this list
            n_temp_list = len(temp_files_list)

            # Wrap in try-statement to ensure files are closed
            try:
                # Open all temporary exposure HDF5-files in this list
                temp_df = vaex.open_many(temp_files_list)

                # Add to master_df if it exists
                if path.exists(ARGS.master_exp_file):
                    # Open the master exposure file
                    master_df = vaex.open(ARGS.master_exp_file)
                    master_df = master_df.concat(temp_df)
                    temp_files_list.append(ARGS.master_exp_file)
                else:
                    master_df = temp_df

                # Export to HDF5
                master_temp_file = path.join(ARGS.mld, 'temp.hdf5')
                master_df.export_hdf5(master_temp_file)

            # Close all temporary HDF5-files
            finally:
                master_df.close_files()

            # Remove all temporary files
            for temp_file in temp_files_list:
                os.remove(temp_file)

            # Rename master_temp_file to master exposure file name
            os.rename(master_temp_file, ARGS.master_exp_file)

            # Update tqdm iterator
            temp_iter.update(n_temp_list)

        # Close the tqdm iterator
        temp_iter.close()

        # Determine all objids that are known
        print("\nDetermining all objects in the database.")
        try:
            master_df = vaex.open(ARGS.master_exp_file)
            objids, counts = np.unique(master_df['objid'].values,
                                       return_counts=True)
        finally:
            master_df.close()

        # Open master file
        with h5py.File(ARGS.master_file, 'r+') as m_file:
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


# This function processes an exposure file
def process_exp_files(expnum, exp_files):
    # Import vaex
    import vaex

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
        raise_error(f"Exposure file {exp_file!r} contains multiple exposures!")

    # Export vaex DataFrame to HDF5
    exp_file_hdf5 = path.join(ARGS.mld, TEMP_EXP_FILE.format(expnum))
    exp_data.export_hdf5(exp_file_hdf5)

    # Open master file
    with h5py.File(ARGS.master_file, 'r+') as m_file:
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
def check_database_exists(req):
    # Check if the database exists
    exists = path.exists(ARGS.mld)

    # If exists and req are not equal, raise error
    if req is not exists:
        # If database exists
        if exists:
            raise_error(f"Provided DIR {ARGS.dir!r} already contains a "
                        f"micro-lensing database!")
        # If database does not exist
        else:
            raise_error(f"Provided DIR {ARGS.dir!r} does not contain a "
                        f"micro-lensing database!")

    # If database exists, check version and remove stale lock-files
    if exists and path.exists(ARGS.master_file):
        check_version()
        remove_stale_lock_files()


# This function checks the version of the database against installed version
def check_version():
    """


    """

    # Obtain the version of the database
    with h5py.File(ARGS.master_file, 'r') as m_file:
        mld_version = m_file.attrs['version']

    # Check if package version is older than the database version
    if(parse_version(__version__) < parse_version(mld_version)):
        # If so, raise error and exit
        raise_error(f"Database in provided DIR {ARGS.dir!r} was constructed "
                    f"with a version later than the current version of "
                    f"{PKG_NAME} (v{mld_version} > v{__version__}). Get the "
                    f"latest version of {PKG_NAME} at "
                    f"https://github.com/1313e/MLDatabase to use this "
                    f"database!")


# This function removes all stale lock-files
def remove_stale_lock_files():
    """


    """

    # Obtain all lock-files in mld_dir
    lock_files = glob(path.join(ARGS.mld, ".*.lock"))

    # Loop over all lock_files
    for lock_file in lock_files:
        # Obtain stats on this lock_file
        stat = os.stat(lock_file, follow_symlinks=False)

        # Obtain creation time of lock_file
        st_ctime = stat.st_ctime

        # Obtain current time
        ctime = time.time()

        # If lock_file is more than a week old, remove it
        if(ctime-st_ctime >= 604800):
            os.remove(lock_file)


# This function raises an error properly, depending on how the database is used
def raise_error(message):
    # Check the value of CLI_flag and act accordingly
    if ARGS.CLI_flag:
        print(f"ERROR: {message}")
        sys.exit()
    else:
        raise OSError(message)


# This function creates a generator that returns dynamically sized slices
def dyn_range(n, step=100):
    """
    Generator that returns slices of range `step` for indexing an object of
    length `n`. The last slice has a range of up to `step*1.5`.

    Parameters
    ----------
    n : int
        The length of the object the slices will be used for.

    Optional
    --------
    step : int. Default: 100
        The step size of each slice.

    """

    # Calculate step_max
    step_max = int(step*1.5)

    # Initialize upper limit
    b = 0

    # Keep generating new slices until n has been reached
    while(b < n):
        # Set lower limit to previous upper limit
        a = b

        # Increase upper limit by step except if less than step_max remain
        b += step_max if(n-b <= step_max) else step

        # Make sure upper limit is not higher than n
        b = min(b, n)

        # Return the next slice
        yield(slice(a, b))


# %% MAIN FUNCTION
def main():
    """

    """

    # Initialize argparser
    parser = argparse.ArgumentParser(
        'mld',
        description=main_desc,
        formatter_class=HelpFormatterWithSubCommands,
        add_help=True,
        allow_abbrev=True)

    # Add subparsers
    subparsers = parser.add_subparsers(
        title='commands',
        metavar='COMMAND')

    # OPTIONAL ARGUMENTS
    # Add 'version' argument
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f"{PKG_NAME} v{__version__}")

    # Add 'dir' argument
    parser.add_argument(
        '-d', '--dir',
        help="Micro-lensing database directory to use",
        metavar='DIR',
        action='store',
        default=path.abspath('.'),
        type=str,
        dest='dir')

    # Create a parent parser for 'init', 'reset' and 'update' commands
    parent_parser = argparse.ArgumentParser(add_help=False)

    # Add optional 'nexpnums' argument
    parent_parser.add_argument(
        '-n', '--n_expnums',
        help="Number of exposures to use",
        metavar='N',
        action='store',
        default=None,
        type=int,
        dest='n_expnums')

    # INIT COMMAND
    # Add init subparser
    init_parser = subparsers.add_parser(
        'init',
        parents=[parent_parser],
        description="Initialize a new micro-lensing database in DIR",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=True)

    # Set defaults for init_parser
    init_parser.set_defaults(func=cli_init)

    # IPYTHON COMMAND
    # Add IPython subparser
    ipython_parser = subparsers.add_parser(
        'ipython',
        description=("Start an embedded IPython console to interact with an "
                     "existing micro-lensing database in DIR"),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=True)

    # Set defaults for ipython_parser
    ipython_parser.set_defaults(func=cli_ipython)

    # RESET COMMAND
    # Add reset subparser
    reset_parser = subparsers.add_parser(
        'reset',
        parents=[parent_parser],
        description=("Delete and reinitialize an existing micro-lensing "
                     "database in DIR"),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=True)

    # Set defaults for reset_parser
    reset_parser.set_defaults(func=cli_reset)

    # STATUS COMMAND
    # Add status subparser
    status_parser = subparsers.add_parser(
        'status',
        description="Show the status of the micro-lensing database in DIR",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=True)

    # Set defaults for status_parser
    status_parser.set_defaults(func=cli_status)

    # UPDATE COMMAND
    # Add update subparser
    update_parser = subparsers.add_parser(
        'update',
        parents=[parent_parser],
        description="Update an existing micro-lensing database in DIR",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=True)

    # Set defaults for update_parser
    update_parser.set_defaults(func=cli_update)

    # Parse the arguments
    global ARGS
    ARGS = parser.parse_args()

    # Make sure provided dir is an absolute path
    ARGS.dir = path.abspath(ARGS.dir)

    # Check if provided dir exists
    if not path.exists(ARGS.dir):
        # If not, raise error and exit
        print(f"ERROR: Provided DIR {ARGS.dir!r} does not exist!")
        sys.exit()

    # Obtain absolute path to database
    ARGS.mld = path.join(ARGS.dir, MLD_NAME)
    ARGS.master_file = path.join(ARGS.mld, MASTER_FILE)
    ARGS.master_exp_file = path.join(ARGS.mld, MASTER_EXP_FILE)

    # Set CLI_flag to True
    ARGS.CLI_flag = True

    # If arguments is empty (no func was provided), show help
    if 'func' not in ARGS:
        parser.print_help()
    # Else, call the corresponding function
    else:
        # Make sure that the current user permission mask is set properly
        os.umask(0o002)
        ARGS.func()


# %% MAIN EXECUTION
if(__name__ == '__main__'):
    main()
