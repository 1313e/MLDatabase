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
from traceback import print_exc

# Package imports
import IPython
import h5py
import numpy as np
import pandas as pd
import prompt_toolkit as ptk
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.validation import DummyValidator
from tqdm import tqdm
import vaex

# MLDatabase imports
from mldatabase import (
    __version__, EXIT_KEYWORDS, EXP_HEADER, EXP_REGEX, MASTER_EXP_FILE,
    MASTER_FILE, MLD_NAME, PKG_NAME, REQ_FILES, SIZE_SUFFIXES, TEMP_EXP_FILE,
    XTR_HEADER)

# All declaration
__all__ = ['main']


# %% GLOBALS
# Define global arguments that holds all arguments given to parser
global ARGS

# Define list of all query keywords
QUERY_KEYWORDS = []


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
def cli_init():
    # Check if a database already exists in this folder
    check_database_exist(False)

    # Check if these files are present
    for req_file in REQ_FILES:
        if not path.exists(path.join(ARGS.dir, req_file)):
            # If not, raise error and exit
            print(f"ERROR: Provided DIR {ARGS.dir!r} does not contain required"
                  f" files for micro-lensing database!")
            sys.exit()

    # Make the database directory
    print(f"Initializing micro-lensing database in {ARGS.dir!r}.")
    os.mkdir(ARGS.mld)

    # Update the database
    cli_update()


# This function handles the 'ipython' subcommand
def cli_ipython():
    # Check if a database already exists in this folder
    check_database_exist(True)

    # Load the database
    df = vaex.open(ARGS.master_exp_file)

    # Embed an IPython console
    IPython.embed(
        banner1=("Starting IPython session. Database is available as 'df', a "
                 "vaex DataFrame.\n"
                 "See https://vaex.readthedocs.io/en/latest/tutorial.html "
                 "for how to interact with vaex DataFrames.\n"),
        exit_msg="Leaving IPython session. Database will be closed.",
        colors='Neutral',
        user_ns={'df': df})

    # Close DataFrame after IPython session has ended
    df.close_files()


# This function handles the 'query' subcommand
def cli_query():
    # Check if a database already exists in this folder
    check_database_exist(True)

    # Load the database
    df = vaex.open(ARGS.master_exp_file)

    # Add df to ARGS
    ARGS.df = df

    # Wrap in try-statement to ensure DataFrame is closed afterward
    try:
        # Create list of valid keywords
        keywords = [*EXIT_KEYWORDS, *QUERY_KEYWORDS]

        # Initialize CLI objects
        # TODO: Write auto-suggest only matching against allowed words
        auto_suggest = AutoSuggestFromHistory()
        completer = WordCompleter(keywords)
        validator = DummyValidator()

        # Start session
        session = ptk.PromptSession(
            message='query> ',
            bottom_toolbar=("Type 'help' for an overview of all valid "
                            "keywords. Type 'exit' to exit the session."),
            history=FileHistory(path.join(ARGS.mld, 'history.txt')),
            enable_history_search=True,
            auto_suggest=auto_suggest,
            completer=completer,
            complete_while_typing=False,
            validator=validator,
            validate_while_typing=True)

        # Keep looping over the prompts until exited by the user
        while True:
            # Wrap in try-statement to catch and simply print exception
            try:
                # Prompt for an input from the user
                inputs = session.prompt()

                # Check if the user wants to exit, and break the loop if so
                if inputs in EXIT_KEYWORDS:
                    break

                # Process the inputs of the user
                process_query_inputs(inputs)

            # If an exception is raised, simply print the entire traceback
            except Exception:
                print_exc()

    # Close DataFrame after query session has ended
    finally:
        df.close_files()


# This function handles the 'reset' subcommand
def cli_reset():
    # Check if a database already exists in this folder
    check_database_exist(True)

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
def cli_update():
    # Check if a database already exists in this folder
    check_database_exist(True)
    print(f"Updating micro-lensing database in {ARGS.dir!r}.")

#    # Obtain path to reference exposure file
#    ref_exp_file = path.join(ARGS.dir, 'Exp0.csv')

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
    with h5py.File(ARGS.master_file, mode='a') as m_file:
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
    filenames = str(sorted(next(os.walk(ARGS.dir))[2]))
#    filenames = str(sorted(next(os.walk(ARGS.dir))[2])[:10])   # Only select the first 10 files found

    # Create a regex iterator
    re_iter = re.finditer(EXP_REGEX, filenames)

    # Create dict with all exposure files
    exp_dict = {int(m['expnum']): (path.join(ARGS.dir, m['exp_file']),
                                   path.join(ARGS.dir, m['xtr_file']))
                for m in re_iter}

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
    print(f"Found {n_expnums:,} exposure files, of which {n_expnums_new:,} are"
          f" new and {n_expnums_outdated:,} are outdated.")

    # If exp_dict or temp_files contains at least 1 item
    if exp_dict or temp_files:
        # Create tqdm iterator for processing
        exp_iter = tqdm(exp_dict.items(), desc="Processing exposure files",
                        dynamic_ncols=True)

        # Open master file
        with h5py.File(ARGS.master_file, 'r+') as m_file:
            # Process all exposure files
            try:
                for expnum, exp_files in exp_iter:
                    # Set which exposure is being processed in exp_iter
                    exp_iter.set_postfix_str(path.basename(exp_files[0]))

                    # Process this exposure
                    temp_files.append(
                        process_exp_files(m_file, expnum, exp_files))

            # If a KeyboardInterrupt is raised, update database with progress
            except KeyboardInterrupt:
                print("WARNING: Processing has been interrupted. Updating "
                      "database with currently processed exposures.")

            # Obtain the total number of exposures now
            n_expnums_known = m_file.attrs['n_expnums']

        # Update database
        print("Updating database with processed exposures (NOTE: This may take"
              " a while for large databases.).")

        # Divide temp_files up into lists of length 100
        temp_files = [temp_files[i:i+100]
                      for i in range(0, len(temp_files), 100)]

        # If the master exposure file exists and there are outdated exposures
        if path.exists(ARGS.master_exp_file) and expnums_outdated:
            # Open the master exposure file
            master_df = vaex.open(ARGS.master_exp_file)

            # Solely select the exposures that were not outdated
            for expnum in expnums_outdated:
                master_df = master_df.filter(master_df.expnum != expnum, 'and')

            # Extract the master DataFrame
            master_df = master_df.extract()

            # Export to HDF5
            master_temp_file = path.join(ARGS.mld, 'temp.hdf5')
            master_df.export_hdf5(master_temp_file)

            # Close master file
            master_df.close()

            # Remove original master file
            os.remove(ARGS.master_exp_file)

            # Rename master_temp_file to master exposure file name
            os.rename(master_temp_file, ARGS.master_exp_file)

        # Loop over all temporary exposure HDF5-files
        # TODO: Figure out how to avoid copying over all the data every time
        for temp_files_list in temp_files:
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
            master_df.close_files()

            # Remove all temporary files
            for temp_file in temp_files_list:
                os.remove(temp_file)

            # Rename master_temp_file to master exposure file name
            os.rename(master_temp_file, ARGS.master_exp_file)

        # Determine all objids that are known
        print("Determining all objects in the database.")
        master_df = vaex.open(ARGS.master_exp_file)
        objids, counts = np.unique(master_df['objid'].values,
                                   return_counts=True)
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


# %% FUNCTION DEFINITIONS
# This function processes an exposure file
def process_exp_files(m_file, expnum, exp_files):
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
    exp_file_hdf5 = path.join(ARGS.mld, TEMP_EXP_FILE.format(expnum))
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
def check_database_exist(req):
    # Check if the database exists
    exists = path.exists(ARGS.mld)

    # If exists and req are equal, return
    if req is exists:
        return

    # Else, raise the proper error
    else:
        # If database exists
        if exists:
            print(f"ERROR: Provided DIR {ARGS.dir!r} already contains a "
                  f"micro-lensing database!")
            sys.exit()
        # If database does not exist
        else:
            print(f"ERROR: Provided DIR {ARGS.dir!r} does not contain a "
                  f"micro-lensing database!")
            sys.exit()


# %% QUERY FUNCTIONS
# This function processes the inputs given by the user in the query session
def process_query_inputs(inputs):
    raise ValueError("LOL, w00t?")


# This function handles the 'help' query
def query_help(inputs):
    pass


# This function handles the 'param' query
def query_param(inputs):
    pass


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

    # QUERY COMMAND
    # Add query subparser
    query_parser = subparsers.add_parser(
        'query',
        description="Query an existing micro-lensing database in DIR",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=True)

    # Set defaults for query_parser
    query_parser.set_defaults(func=cli_query)

    # RESET COMMAND
    # Add reset subparser
    reset_parser = subparsers.add_parser(
        'reset',
        description=("Delete and reinitialize an existing micro-lensing "
                     "database in DIR"),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=True)

    # Set defaults for reset_parser
    reset_parser.set_defaults(func=cli_reset)

    # SEARCH COMMAND
    # Add search subparser
    search_parser = subparsers.add_parser(
        'search',
        description="Alias for 'query'",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=True)

    # Set defaults for search_parser
    search_parser.set_defaults(func=cli_query)

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

    # If arguments is empty (no func was provided), show help
    if 'func' not in ARGS:
        parser.print_help()
    # Else, call the corresponding function
    else:
        ARGS.func()


# %% MAIN EXECUTION
if(__name__ == '__main__'):
    main()
