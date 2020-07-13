MLDatabase
==========
*MLDatabase* is a Python 3 CLI-package for managing the DECam exposure CSV-files and creating a micro-lensing event database.

Installation & Use
==================
How to install
--------------
*MLDatabase* can be easily installed by cloning the `repository`_ and installing it manually (note that it requires Python 3.6+)::

    $ git clone https://github.com/1313e/MLDatabase
    $ cd MLDatabase
    $ pip install .

.. _repository: https://github.com/1313e/MLDatabase

Example use
-----------
From the command line
+++++++++++++++++++++
*MLDatabase* can be used from the command line with the command ``mld``.
Calling this from the command line with no arguments at all, will show the help overview describing the different commands it takes.
It takes an optional ``-d``/``--dir`` argument (which defaults to the current directory) which is the directory containing all the DECam exposure files in CSV-format.
This directory is referred to as ``DIR``.

The three most important commands (``mld init``; ``mld update``; and ``mld ipython``) are described below.

Initializing a database
#######################
A database can be created with the command ``mld init`` in a proper directory ``DIR``.
Calling this command in a directory that does not contain the proper files or already contains a micro-lensing database, will result in an error stating why a database cannot be created.
If the database can be created, several files required for the database will be created in the hidden ``.mldatabase`` directory.
After a database has been initialized, it will be immediately updated with the ``mld update`` command.

Updating a database
###################
Existing databases can be updated with the ``mld update`` command.
Calling this command when no database exists in ``DIR`` will result in an error.

When updating a database, the program determines all DECam exposure CSV-files in ``DIR`` that are valid according to a list of conditions.
By default, all exposures that the program can find will be used, but you can, for example, only select the first 10 exposures that it can find with ``mld update -n 10`` (``-n`` can also be used with any command that calls ``mld update``, e.g., ``mld init`` and ``mld reset``).
It then compares this list of exposures against all exposures the database already knows about.
All exposures that are either missing (the exposure data is not included in the database) or outdated (the exposure data was updated after it was included) will be added to the database.

Exposures that must be added to the database are processed one-by-one.
When an exposure is processed, the database records the last modified date of the CSV-file that belongs to it, which is used to determine outdated exposures.
As the processing of exposure files can take a while for large numbers of exposures, it can be safely interrupted if you wish.
Interrupting this process will cause the program to stop processing them and start updating the database with all processed exposures.

After all exposures have been processed (or it was interrupted), the database is updated with them.
This process can be safely interrupted as well if necessary, which causes all remaining processed exposures to be added to the database during the next update.

While a database is being updated, none can access the database in any way that is provided by the *MLDatabase* package (e.g., with the ``mld ipython`` command or with the ``open_database`` context manager described below) or execute the ``mld update`` and ``mld reset`` commands.
Custom files called lock-files, which can only be modified by its owner, are created by the program to ensure that this does not happen.
The database itself is always created in such a way that it can be used and modified by any user that can access the directory it lives in.

Accessing a database
####################
When a database has been created with ``mld init``, it can be accessed using the ``mld ipython`` command.
This command starts a special IPython session in the terminal that provides safe access to the database.
The IPython session starts with the database already being available in the namespace, which is a vaex DataFrame called ``df``.
See https://vaex.readthedocs.io/en/latest/tutorial.html for how to interact with them.

In this IPython session, the database can be interacted with using any of the functions, methods, etc. that a vaex DataFrame accepts.
Below is a small example script for interacting with the database in a few different ways:

.. code:: python

    # Filter all objects with objid == 5000 and return it
    >>> obj = df[df.objid == 5000]

    # Obtain the column that holds the magnitude values
    >>> mags = obj.mag

    # Calculate mean and standard deviation of the magnitudes
    >>> mean_mag = mags.mean()
    >>> std_mag = mags.std()

    # Internally select all objects with mags more than 3 sigmas below the mean
    >>> obj.select(mags < (mean_mag-3*std_mag))

    # Internally select all objects with mags within 3 sigmas of the mean
    >>> obj.select(mags > (mean_mag-3*std_mag))
    >>> obj.select(mags < (mean_mag+3*std_mag), mode='and')

    # Obtain the NumPy array of HJDs that satisfies the current selection
    >>> hjds = obj.evaluate(obj.hjd, selection=True)

    # Obtain the magnitude values as a NumPy array, ignoring selection
    >>> mag_vals = obj.evaluate(mags)

Any modifications made to the database in this IPython session, are discarded after the session closes.
While a database is being accessed using this command (or with the ``open_database`` context manager described below), the database cannot be modified using the ``mld update`` or ``mld reset`` commands.
As described earlier, lock-files are used to ensure that this does not happen.
The database can however be accessed in multiple different processes simultaneously with no problems.
All of these processes must be closed before the database can be modified.


Within a Python script
++++++++++++++++++++++
It is also possible to access an existing database from within a Python script using the ``open_database`` context manager.
This context manager (see `here <https://docs.python.org/3/reference/datamodel.html#context-managers>`_ for info) allows for an existing database to be safely accessed from within any Python script (or a normal IPython session if you wish) in the same way as the ``mld ipython`` command.

The context manager takes a single optional argument ``exp_dir``, which is equivalent to the optional ``-d``/``--dir`` argument when using the command line interface.
As with the ``mld ipython`` command, this context manager yields the database as a vaex DataFrame object.
See https://vaex.readthedocs.io/en/latest/tutorial.html for how to interact with them.

Below is the same example script used above, but this time using the context manager for accessing the database:

.. code:: python

    # Imports
    from mldatabase import open_database


    # Open database
    # The default value is to use the current working directory
    with open_database() as df:
        # Filter all objects with objid == 5000 and return it
        obj = df[df.objid == 5000]

        # Obtain the column that holds the magnitude values
        mags = obj.mag

        # Calculate mean and standard deviation of the magnitudes
        mean_mag = mags.mean()
        std_mag = mags.std()

        # Internally select all objects with mags more than 3 sigmas below the mean
        obj.select(mags < (mean_mag-3*std_mag))

        # Internally select all objects with mags within 3 sigmas of the mean
        obj.select(mags > (mean_mag-3*std_mag))
        obj.select(mags < (mean_mag+3*std_mag), mode='and')

        # Obtain the NumPy array of HJDs that satisfies the current selection
        hjds = obj.evaluate(obj.hjd, selection=True)

        # Obtain the magnitude values as a NumPy array, ignoring selection
        mag_vals = obj.evaluate(mags)

    # After exiting the with-block, the database is closed
    # Any attempts to access the database will result in a 'Segmentation fault'
