"""
CLI
"""

import argparse
import re
import sys
import traceback
from pathlib import Path

from .create_box_file import create_box_file
from .env import (
    DEFAULT_PYTHON_INTERPRETER,
    get_bentobox_version,
)
from .util import load_py_module
from .box_file import (
    wrap_single,
    wrap_multiple,
    WrapInfo,
    WrapMode,
)


RE_BOX_NAME = re.compile(r"^\w+(?:[\-\w+])*$")

def t_box_name(value):
    if not RE_BOX_NAME.match(value):
        raise ValueError(value)
    return value


def t_python_exe(value):
    if not value.startswith('/'):
        raise ValueError("{!r} is not an absolute path")
    return value


def function_create(box_name, wrap_info, output_path,
                    packages, update_shebang, check,
                    python_interpreter, force_overwrite,
                    verbose_level, pip_install_args,
                    freeze_env, freeze_pypi):
    # pylint: disable=too-many-arguments
    create_box_file(box_name, output_path=output_path, wrap_info=wrap_info,
                    pip_install_args=pip_install_args,
                    freeze_env=freeze_env, freeze_pypi=freeze_pypi,
                    packages=packages, update_shebang=update_shebang,
                    check=check, python_interpreter=python_interpreter,
                    force_overwrite=force_overwrite,
                    verbose_level=verbose_level)


def function_show(box_path, mode="text"):
    box_module = load_py_module(box_path)
    box_module.show(mode=mode)  # pylint: disable=no-member


def booldef(bool_value, kwargs):
    if bool_value == kwargs['default']:
        return ' (default)'
    return ''


def add_create_parser(subparsers):
    parser = subparsers.add_parser(
        "create",
        description="""\
Create a box file
""")
    parser.set_defaults(
        function=function_create,
        function_args=['box_name', 'wrap_info', 'output_path',
                       'packages', 'update_shebang', 'check', 'python_interpreter',
                       'force_overwrite', 'pip_install_args',
                       'freeze_env', 'freeze_pypi', 'verbose_level']
    )
    default_verbose_level = 0
    verbose_level_group = parser.add_argument_group("verbose")
    verbose_level_mgrp = verbose_level_group.add_mutually_exclusive_group()
    verbose_level_kwargs = {'dest': 'verbose_level', 'default': default_verbose_level}
    verbose_level_mgrp.add_argument(
        "-q", "--quiet",
        action="store_const", const=0,
        help="quiet mode (set verbose level to 0)",
        **verbose_level_kwargs)
    verbose_level_mgrp.add_argument(
        "-v", "--verbose",
        action="count",
        help="increase verbose level",
        **verbose_level_kwargs)
    verbose_level_mgrp.add_argument(
        "-V", "--verbose-level",
        type=int,
        help="set verbose level",
        **verbose_level_kwargs)

    parser.add_argument(
        "-O", "--force-overwrite",
        action="store_true", default=False,
        help="overwrite file if it exists")

    box_group = parser.add_argument_group("box parameters")
    wrap_info_mgrp = box_group.add_mutually_exclusive_group(required=True)
    wrap_info_kwargs = {'dest': 'wrap_info'}
    wrap_info_mgrp.add_argument(
        "-w", "--wrap-command",
        metavar="COMMAND",
        help="wrap a single installed COMMAND",
        type=wrap_single,
        **wrap_info_kwargs)
    wrap_info_mgrp.add_argument(
        "-W", "--wrap-commands",
        metavar="COMMAND",
        type=wrap_multiple,
        help="wrap multiple installed COMMANDS",
        **wrap_info_kwargs)
    wrap_info_mgrp.add_argument(
        "-A", "--wrap-all-installed-commands",
        action="store_const", const=WrapInfo(WrapMode.ALL, None),
        help="wrap all installed commands",
        **wrap_info_kwargs)
    wrap_info_mgrp.add_argument(
        "-N", "--no-wrap",
        action="store_const", const=WrapInfo(WrapMode.NONE, None),
        help="no wrapping (create an installer box)",
        **wrap_info_kwargs)

    box_group.add_argument(
        "-a", "--pip-install-arg",
        dest="pip_install_args",
        metavar="ARG",
        action="append",
        default=None,
        help="add pip install arg")

    python_mgrp = box_group.add_mutually_exclusive_group()
    python_kwargs = {'dest': 'python_interpreter', 'default': DEFAULT_PYTHON_INTERPRETER}
    python_current = str(Path(sys.executable).absolute())
    python_mgrp.add_argument(
        "-P", "--current-python",
        action="store_const", const=python_current,
        help=("use current python interpreter {p!r} as shebang " +
              "in the script".format(p=python_current)),
        **python_kwargs)
    python_mgrp.add_argument(
        "-p", "--python",
        metavar="PYTHON",
        type=t_python_exe,
        help="string to be used as shebang in the script " + \
             "(defaults to {d!r})".format(d=DEFAULT_PYTHON_INTERPRETER),
        **python_kwargs)

    check_mgrp = box_group.add_mutually_exclusive_group()
    check_kwargs = {'dest': 'check', 'default': True}
    check_mgrp.add_argument(
        "-c", "--check",
        action="store_true",
        help="check box setup and configuration" + booldef(True, check_kwargs),
        **check_kwargs)
    check_mgrp.add_argument(
        "-C", "--no-check",
        action="store_false",
        help="do not check box" + booldef(False, check_kwargs),
        **check_kwargs)

    update_shebang_mgrp = box_group.add_mutually_exclusive_group()
    update_shebang_kwargs = {'dest': 'update_shebang', 'default': True}
    update_shebang_mgrp.add_argument(
        "-u", "--shebang-update",
        action="store_true",
        help="update shebang when installing" + booldef(True, update_shebang_kwargs),
        **update_shebang_kwargs)
    update_shebang_mgrp.add_argument(
        "-U", "--no-shebang-update",
        action="store_false",
        help="do not update shebang when installing" + booldef(False, update_shebang_kwargs),
        **update_shebang_kwargs)

    freeze_env_mgrp = box_group.add_mutually_exclusive_group()
    freeze_env_kwargs = {'dest': 'freeze_env', 'default': True}
    freeze_env_mgrp.add_argument(
        "-e", "--freeze-env",
        action="store_true",
        help="freeze virtualenv environment" + booldef(True, freeze_env_kwargs),
        **freeze_env_kwargs)
    freeze_env_mgrp.add_argument(
        "-E", "--no-freeze-env",
        action="store_false",
        help="do not freeze virtualenv environment" + booldef(False, freeze_env_kwargs),
        **freeze_env_kwargs)

    freeze_pypi_mgrp = box_group.add_mutually_exclusive_group()
    freeze_pypi_kwargs = {'dest': 'freeze_pypi', 'default': True}
    freeze_pypi_mgrp.add_argument(
        "-f", "--freeze-pypi",
        action="store_true",
        help="download packages from PyPI along with their dependencies" + \
             booldef(True, freeze_pypi_kwargs),
        **freeze_pypi_kwargs)
    freeze_pypi_mgrp.add_argument(
        "-F", "--no-freeze-pypi",
        action="store_false",
        help="do not download packages from PyPI" + \
             booldef(False, freeze_pypi_kwargs),
        **freeze_pypi_kwargs)

    parser.add_argument(
        "-o", "--output-path",
        type=Path,
        default=None,
        help="box path")

    parser.add_argument(
        "-n", "--box-name",
        type=t_box_name,
        required=True,
        help="box name")

    parser.add_argument(
        "packages",
        metavar="package",
        nargs="*",
        default=[],
        help="install python packages")
    return parser


def add_show_parser(subparsers):
    parser = subparsers.add_parser(
        "show",
        description="""\
Show a box file
""")
    parser.set_defaults(
        function=function_show,
        function_args=["box_path", "mode"],
    )
    mode_group = parser.add_argument_group("mode")
    mode_mgrp = mode_group.add_mutually_exclusive_group()
    default_mode = "json"
    mode_mgrp.add_argument(
        "-j", "--json",
        dest="mode", default=default_mode,
        action="store_const", const="json",
        help="json output")
    mode_mgrp.add_argument(
        "-t", "--text",
        dest="mode", default=default_mode,
        action="store_const", const="text",
        help="text output (default)")
    parser.add_argument(
        "box_path",
        type=Path,
        help="path of the box file")
    return parser


# def add_help_parser(subparsers):
#     parser = subparsers.add_parser(
#         "help",
#         description="""\
# Help about bentobox
# """)
#     parser.set_defaults(
#         function=function_help,
#         function_args=['topics'],
#     )
#     parser.add_argument(
#         "topics",
#         nargs="*",
#         choices=list(HELP_TOPICS),
#         default=['main'],
#         help="available help topics")
#     return parser


def main():
    parser = argparse.ArgumentParser(
        description="""\
Bentobox {version} - create python boxes
""".format(version=get_bentobox_version())
    )
    parser.set_defaults(
        function=parser.print_help,
        function_args=[],
    )
    parser.add_argument(
        "-t", "--trace",
        action="store_true", default=False,
        help=argparse.SUPPRESS)

    subparsers = parser.add_subparsers()

    add_create_parser(subparsers)
    add_show_parser(subparsers)
    # add_help_parser(subparsers)

    namespace = parser.parse_args()
    trace = namespace.trace

    function = namespace.function
    function_kwargs = {arg: getattr(namespace, arg) for arg in namespace.function_args}

    try:
        result = function(**function_kwargs)
    except Exception as err:  # pylint: disable=broad-except
        if trace:
            traceback.print_exc()
        print("ERR: {}: {}".format(type(err).__name__, err), file=sys.stderr)
        return 2
    if result is None:
        result = 0
    return result
