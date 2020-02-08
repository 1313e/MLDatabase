MLDatabase
==========
*MLDatabase* is a Python 3 CLI-package for managing the DECam exposure CSV-exposure files and creating a micro-lensing event database.

Installation & Use
==================
How to install
--------------
*MLDatabase* can be easily installed by cloning the `repository`_ and installing it manually::

    $ git clone https://github.com/1313e/MLDatabase
    $ cd MLDatabase
    $ pip install .

.. _repository: https://github.com/1313e/MLDatabase

Example use
-----------
*MLDatabase* can be used from the command line with the command ``mld``.
Calling this from the command line with no arguments at all, will show the help overview describing the different commands it takes.
It takes a ``DIR`` argument (which defaults to the current directory) which is the directory containing all the DECam exposure files in CSV-format.
A database can be created with the command ``mld init`` in the proper directory.
