Bentobox
========

Create self-installable python programs

What is bentobox
----------------

Bentobox is a command-line tool to create self-installable python programs.

A bento *box* is a single executable file containing instructions to install
some python packages. These can be online pypi packages, or bundled python
distributions (for instance, a source distribution .tar.gz or a wheel)

For instance, the following command creates a 'bumpversion' executable
file:

::

  $ bentobox create -n bumpversion -w bumpversion bumpversion

The created **bumpversion** executable wraps the bumpversion program, which
is provided by the bumpversion pypi package (see
`bumpversion https://pypi.org/project/bumpversion/`_). The first execution of the
bumpversion executable installs all the necessary packages (only
bumpversion in this case) and runs it. So, the first execution can be slow;
but the following executions are much faster, since the box is already
installed (the default install dir is ``~/.bentobox/boxes/bumpversion``).

::

  $ ./bumpversion -h
  usage: bumpversion [-h] [--config-file FILE] [--verbose] [--list]
  ...

Bundled packages
----------------

Moreover, bentobox can bundle local distributions in the box file. Suppose
you have a local python package **calc**, which is not on pypi, and which
imports another local package **calclib**. The calc package provides a *calc*
program.

You can the run the following command:

::

  $ bentobox create -n calc -w calc \
                 calclib/dist/calclib-1.2.0.tar.gz \
                 calc/dist/calc-0.9.2.tar.gz
  $ ./calc 4 + 6
  CALC> 4 + 6 = 10

The ``./calc`` executable bundles the two necessary python distributions, so it
can be transferred on other computers and run. All you need on the running host
is a python3 interpreter.

In you provide as argument a directory containing a setup.py, the pybox
command will automatically create the distribution file to be bundled:

::

  $ pybox create calc-box -w calc calclib/ calc/
  $ ./calc-box 4 + 6
  CALC> 4 + 6 = 10

Notice that for local pakcages a ``/`` in the path is necessary: if a
package name does not contain a ``/``, it is considered a pypi package.

The installation phase
----------------------

Any created box file is a python3 executable; the default shebang is

::

  #!/usr/bin/env python3

This can be changed with the bentobox command line options *-P* and *-p*
(see ``bentobox --help``).

Anyway, normally boxes are transferred to remote hosts; the remote python
interpreter my have non standard names or installation paths.

For instance, suppose you create a box file on *host1*, where a python3
interpreter is available on standard system paths:

::

  [host1] $ bentobox create -n say_hello -w say_hello \
                                 helloworld-1.0.0.tar.gz

Then, you transfer the box file on *host2*, where python3 is available under a
non-standard installation path, ``/opt/software/python``:

::

  [host2] $ ./say_hello World
  /usr/bin/env: 'python3': No such file or directory

So you have to properly call the python interpreter:

::

  [host2] $ env LD_LIBRARY_PATH=/opt/software/python/lib:$LD_LIBRARY_PATH \
                /opt/software/python/bin/python3 ./say_hello World
  Hello, world!
  
During this first invocation the install phase is executed; the say_hello
box is installed under ``~/.bentobox/boxes/say_hello``, the the *helloworld*
package is installed in a virtualenv (``~/.bentobox/boxes/say_hello/virtualenv``).
After the installation, the ``./say_hello``'s shebang is replaced by

::

  #!/home/user/.bentobox/boxes/say_hello/virtualenv/bin/python3
   
so that you don't need to explicitly call the python interpreter again.
Moreover, there is no need to set the LD_LIBRARY_PATH: indeed at
installation bentobox freezes the virtualenv's python executable by saving the
current $LD_LIBRARY_PATH:

::

  [host2] $ ./say_hello World
  Hello, world!


Single-command box
------------------

All the examples above create single-command boxes; they fully wraps a single
installed command, which is passed through the ``-w`` option.

A single-command box has the same interface of the wrapped command.

Sometimes more than one command is installed and must be made accessible. For instance,
the ``simple-calc`` installs the following commands:

 * ``simple-add``
 * ``simple-sub``
 * ``simple-mul``
 * ``simple-div``
 * ``simple-pow``
 * ``simple-calc``

If you want to wrap all of them you can create a single-command box for each command to wrap; if
you specify the same box name, they all will share the same installation directory. For instance:

::

  $ bentobox create -n simple-calc -w simple-add -o simple-add simple-calc-0.0.1.tar.gz
  $ bentobox create -n simple-calc -w simple-mul -o simple-mul simple-calc-0.0.1.tar.gz

  $ ./simple-add 2 3
  SIMPLE-ADD> 2 + 3 = 5
  $ ./simple-mul 2 3
  SIMPLE-MUL> 2 x 3 = 6
  
The first command ``./first-add 2 3`` will take some time to install the box; the second command
is faster, since the box is already installed.

Anyway, in such cases, a multiple-command box can be created.
  
Multiple-command box
--------------------

A multiple-command box wraps many commands with a single box file; an additional argument is added
to select the command. The ``-W`` option is used instead of ``-w``; the argument is a comma-separated list
of installed command names:

::

  $ bentobox create -n simple-calc -W simple-add,simple-mul simple-calc-0.0.1.tar.gz

  $ ./simple-calc -h
  usage: simple-calc [-h] {simple-add,simple-mul}
  
  simple-calc
  
  positional arguments:
    {simple-add,simple-mul}
  
  optional arguments:
    -h, --help            show this help message and exit
  $ ./simple-calc simple-add 2 3
  SIMPLE-ADD> 2 + 3 = 5
  $ ./simple-calc simple-mul 2 3
  SIMPLE-MUL> 2 x 3 = 6

The ``-W`` argument allows to change the command name:

::

  $ bentobox create -n simple-calc \
    -W add=simple-add,mul=simple-mul,sub=simple-sub,div=simple-div,pow=simple-pow,calc=simple-calc \
    simple-calc-0.0.1.tar.gz

  $ ./simple-calc -h
  usage: simple-calc [-h] {add,calc,div,mul,pow,sub}
  
  simple-calc
  
  positional arguments:
    {add,calc,div,mul,pow,sub}
  
  optional arguments:
    -h, --help            show this help message and exit
  $ ./simple-calc add 2 3
  SIMPLE-ADD> 2 + 3 = 5
  $ ./simple-calc mul 2 3
  SIMPLE-MUL> 2 x 3 = 6
  $ ./simple-calc pow 2 3
  SIMPLE-POW> 2 ^ 3 = 8

The ``-A`` option can be used to create a multiple-command box wrapping all the installed commands. In this case it is not 
possible to change command names:

::

  $ ./simple-calc -h
  usage: simple-calc [-h]
                     {simple-add,simple-calc,simple-div,simple-mul,simple-pow,simple-sub}
  
  simple-calc
  
  positional arguments:
    {simple-add,simple-calc,simple-div,simple-mul,simple-pow,simple-sub}
  
  optional arguments:
    -h, --help            show this help message and exit

Installer box
-------------

An installer box does not wrap any installed command; it can be used to install the box content and to manage it.

::

  $ bentobox create -n simple-calc -N simple-calc-0.0.1.tar.gz -O
  $ ./simple-calc -h
  usage: simple-calc [-h]
                     {show,configure,extract,install,uninstall,list,run} ...
  
  Box simple-calc - manage box
  
  positional arguments:
    {show,configure,extract,install,uninstall,list,run}
  
  optional arguments:
    -h, --help            show this help message and exit

  $ ./simple-calc install
  ################################################################################
  Box 'simple-calc' has been installed.
  ################################################################################
  
  The install dir is:
    /home/user/.bentobox/boxes/simple-calc
  
  To activate the installation run:
    source /home/user/.bentobox/boxes/simple-calc/bentobox-env.sh

The env file can be sources to make the box commands available:

::

  $ source /home/user/.bentobox/boxes/simple-calc/bentobox-env.sh
  $ simple-add 2 3
  SIMPLE-ADD> 2 + 3 = 5

Notice that also single-command and multiple-command boxes install an env file.

The ``configure`` subcommand can be used to change the box itself, or to create a new one.
For instance, you can create a single-command box from it:

::

  $ ./simple-calc configure -o simple-add -w simple-add
  $ ./simple-add 2 3
  SIMPLE-ADD> 2 + 3 = 5

Bentobox environment variables
------------------------------

Single-command and multiple-command boxes normally do not show the *installer* interface;
so, for instance, they cannot be configured.
Anyway, if you have a command box, you can access the installer interface by disabling wrapping; this can be done
by setting the ``BBOX_WRAPPING=off`` environment variable:

::

  $ bentobox create -n simple-calc -w simple-add -o simple-add simple-calc-0.0.1.tar.gz

  $ ./simple-add -h
  usage: simple-add [-h] left right
  
  positional arguments:
    left
    right
  
  optional arguments:
    -h, --help  show this help message and exit

  $ BBOX_WRAPPING=off ./simple-add -h
  usage: simple-add [-h] {show,configure,extract,install,uninstall,list,run} ...
  
  Box simple-calc - manage box
  
  positional arguments:
    {show,configure,extract,install,uninstall,list,run}
  
  optional arguments:
    -h, --help            show this help message and exit
  $ 

The full list of environment variables is:

 * ``BBOX_INSTALL_DIR=/tmp/data``: set the install dir to ``/tmp/data``
 * ``BBOX_WRAPPING=off``: enable/disable wrapping
 * ``BBOX_VERBOSE_LEVEL=1``: set the verbose level to ``1``
 * ``BBOX_DEBUG=on``: enable/disable debug mode
 * ``BBOX_FREEZE=off``: enable/disable freezing of python interpreter
 * ``BBOX_UPDATE_SHEBANG=off``: enable/disable updating of the box shebang
 * ``BBOX_FORCE_REINSTALL=on``: force a reinstall
 * ``BBOX_UNINSTALL=on``: uninstall the box and restores the shebang; command line arguments are ignored
