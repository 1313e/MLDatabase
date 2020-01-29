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

# MLDatabase imports
from . import __version__, MLD_NAME, PKG_NAME

# All declaration
__all__ = ['main']


# %% GLOBALS
# Define the main help docstring
main_description = dedent("")


# %% CLASS DEFINITIONS
# Define formatter that automatically extracts help strings of subcommands
class HelpFormatterWithSubCommands(argparse.HelpFormatter):
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
        parts = [name, desc_lines.pop(0)]

        # Loop over all remaining desc_lines
        for line in desc_lines:
            # Format and add to parts
            parts.append("%s%s\n" % (' '*help_position, line))

        # Convert to a single string and return
        return(''.join(parts))


# %% FUNCTION DEFINITIONS
# THis function handles the 'init' subcommand
def init(args):
    # Obtain the provided directory path
    dir_path = path.abspath(args.dir)

    # Obtain the path to database directory
    mld_path = path.join(dir_path, MLD_NAME)

    # Check if a database already exists in this folder
    if path.exists(mld_path):
        # If so, raise error and return
        print("ERROR: Directory %r already contains a micro-lensing database!"
              % (dir_path))
        sys.exit()
    else:
        # If not, make that directory
        os.mkdir(mld_path)


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

    # Add version argument
    parser.add_argument(
        '-v', '--version',
        action='version',
        version="%s v%s" % (PKG_NAME, __version__))

    # Add subparsers
    subparsers = parser.add_subparsers(
        title='commands',
        metavar='COMMAND')

    # Add init subparser
    init_parser = subparsers.add_parser(
        'init',
        description="Initialize a new micro-lensing database in DIR.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=True)

    # Add sole argument to init subparser
    init_parser.add_argument('dir',
                             help="Directory to initialize database in",
                             metavar='DIR',
                             action='store',
                             default='.',
                             nargs='?',
                             type=str)
    init_parser.set_defaults(func=init)

    # Parse the arguments
    args = parser.parse_args()

    # If arguments is empty (no func was provided), show help
    if 'func' not in args:
        parser.print_help()
    # Else, call the corresponding function
    else:
        args.func(args)


# %% MAIN EXECUTION
if(__name__ == '__main__'):
    main()
