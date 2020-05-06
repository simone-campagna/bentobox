#!/usr/bin/env python3

# WARNING: this is a bentobox-generated file - do not edit!

"""
{
    "version": "0.1.0",
    "box_file_version": 1,
    "box_name": "box-name",
    "python_interpreter": "/usr/bin/env python3",
    "python_interpreter_orig": null,
    "install_dir": null,
    "wrap_mode": "NONE",
    "wraps": null,
    "freeze": true,
    "update_shebang": true,
    "verbose_level": 0,
    "pip_install_args": [],
    "use_pypi": true,
    "init_venv_packages": [
        "setuptools",
        "pip"
    ],
    "packages": [
        "pkg1",
        "pkg2"
    ],
    "repo": {
         "pkg2": {
             "pkg2-0.2.1.tar.gz": "abcd0123"
          }
    }
}
"""

# --- end-of-header ---

import argparse
import collections.abc
import contextlib
import enum
import fcntl
import functools
import io
import json
import logging
import logging.config
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import traceback
import venv

from base64 import b64decode
from pathlib import Path

__all__ = [
    'MARK_END_OF_HEADER',
    'MARK_END_OF_SOURCE',
    'MARK_REPO',
    'HEADER_FILL_LEN',
    'WrapMode',
    'WrapInfo',
    'wrap_single',
    'wrap_multiple',
    'create_header',
    'replace_state',
    'show',
    'check',
    'install',
    'extract',
]

# pylint: disable=too-many-lines

class BoxError(Exception):
    pass


class BoxInternalError(Exception):
    pass


class BoxFileVersionMismatch(Exception):
    pass


class WrapMode(enum.Enum):
    NONE = 0
    SINGLE = 1
    MULTIPLE = 2
    ALL = 3

WrapInfo = collections.namedtuple(  # pylint: disable=invalid-name
    "WrapInfo",
    ["wrap_mode", "wraps"]
)


def wrap_single(value):
    return WrapInfo(WrapMode.SINGLE, value)


def wrap_multiple(value):
    commands = {}
    for item in value.split(','):
        if "=" in item:
            alias, name = item.split("=", 1)
        else:
            alias, name = item, item
        commands[alias] = name
    return WrapInfo(WrapMode.MULTIPLE, commands)


def load_state(json_data):
    """Loads the state"""
    state = json.loads(json_data)
    wrap_mode = WrapMode[state["wrap_mode"]]
    state["wrap_mode"] = wrap_mode
    return state


STATE = load_state(__doc__)

LOG = logging.getLogger(__name__)
VERSION = '0.1.0'

UNDEFINED = object()

HEADER = "[BENTOBOX] "

MARK_END_OF_HEADER = "# --- end-of-header ---"
MARK_END_OF_SOURCE = "# --- end-of-source ---"
MARK_REPO = "# --- repo ---"
HEADER_FILL_LEN = 20 * (80 + 1)

_LOG_STATE = None


# initial values:
VERBOSE_LEVEL = 0

DEBUG_LEVEL = 3

def get_verbose_level(verbose_level=None):
    """Return verbose level"""
    if verbose_level is None:
        verbose_level = VERBOSE_LEVEL
    return verbose_level


def configure_logging(verbose_level=None):
    """Configure global logging"""
    verbose_level = get_verbose_level(verbose_level)
    global _LOG_STATE  # pylint: disable=global-statement
    new_log_state = verbose_level
    if _LOG_STATE == new_log_state:
        return
    if verbose_level >= DEBUG_LEVEL:
        log_level = 'DEBUG'
    elif verbose_level >= 2:
        log_level = 'INFO'
    elif verbose_level >= 1:
        log_level = 'WARNING'
    else:
        log_level = 'ERROR'

    logging.config.dictConfig({
        'version': 1,
        'formatters': {
            'standard': {
                'format': '<BENTOBOX> %(levelname)-10s %(message)s',
                'datefmt': '%Y%m%d %H:%M:%S',
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
            }
        },
        'loggers': {
            __name__: {
                'level': log_level,
            },
        },
        'root': {
            'level': log_level,
            'handlers': ['console'],
        },
    })
    _LOG_STATE = new_log_state


configure_logging()


VarInfo = collections.namedtuple(  # pylint: disable=invalid-name
    "VarInfo",
    ["var_name", "var_type", "var_value", "default", "description"])

ENV_VARS = {}

def get_env_var(var_name, var_type=str, default=None, description=None):
    """Get an environment variable"""
    var_value = _get_env_var(var_name, var_type, default)
    ENV_VARS[var_name] = VarInfo(
        var_name=var_name,
        var_type=var_type,
        var_value=var_value,
        default=default,
        description=description)
    return var_value


def _get_env_var(var_name, var_type=str, default=None):
    """Get an environment variable"""
    value = os.environ.get(var_name, None)
    if value is None:
        return default
    else:
        try:
            return var_type(value)
        except (ValueError, TypeError):
            LOG.warning("%s=%r: invalid value", var_name, value)
            return default


def boolean(value):
    """Make a boolean value from a string"""
    value = value.lower()
    if value in {'on', 'true'}:
        return True
    if value in {'off', 'false'}:
        return False
    return bool(int(value))


INSTALL_DIR = get_env_var(
    "BBOX_INSTALL_DIR", var_type=Path, default=None,
    description="set install dir")
WRAPPING = get_env_var(
    "BBOX_WRAPPING", var_type=boolean, default=True,
    description="enable/disable wrapping")
VERBOSE_LEVEL = get_env_var(
    "BBOX_VERBOSE_LEVEL", var_type=int, default=STATE['verbose_level'],
    description="set verbose level")
FREEZE = get_env_var(
    "BBOX_FREEZE", var_type=boolean, default=STATE['freeze'],
    description="enable/disable freezing virtualenv")
UPDATE_SHEBANG = get_env_var(
    "BBOX_UPDATE_SHEBANG", var_type=boolean, default=STATE['update_shebang'],
    description="enable/disable update of shebang")
UNINSTALL = get_env_var(
    "BBOX_UNINSTALL", var_type=boolean, default=False,
    description="force uninstall")
FORCE_REINSTALL = get_env_var(
    "BBOX_FORCE_REINSTALL", var_type=boolean, default=False,
    description="force reinstall")


configure_logging(VERBOSE_LEVEL)


def default_install_dir():
    """Returns the default install dir"""
    return Path.home() / ".bentobox" / "boxes" / STATE['box_name']


def get_install_dir():
    """Returns the current install dir"""
    if INSTALL_DIR:
        return INSTALL_DIR
    install_dir = STATE['install_dir']
    if install_dir is None:
        install_dir = default_install_dir()
    return Path(install_dir)


def get_config():
    """Get the installed config file, if it exists"""
    config_path = get_install_dir() / 'bentobox-config.json'
    if config_path.is_file():
        with open(config_path, 'r') as config_file:
            config = json.load(config_file)
    else:
        config = None
    return config


def get_wrap_info(state=STATE):
    """Return the WrapInfo"""
    if WRAPPING:
        return WrapInfo(state['wrap_mode'], state['wraps'])
    return WrapInfo(WrapMode.NONE, None)


def get_environ(config):
    """Get the environment for command execution"""
    environ = os.environ.copy()
    old_path = environ.get("PATH", "")
    venv_bin_dir = Path(config['venv_bin_dir'])
    new_path = str(venv_bin_dir.resolve())
    if old_path:
        new_path += ":" + old_path
    environ['PATH'] = new_path
    return environ


def find_executables(bindir=UNDEFINED):
    """Get the list of installed commands, or None if not installed"""
    if bindir is UNDEFINED:
        config = get_config()
        if config is not None:
            return None
        bindir = config["venv_bin_dir"]
    commands = []
    for p_exe in sorted(Path(bindir).iterdir()):
        if p_exe.is_file() and os.access(p_exe, os.X_OK):
            commands.append(p_exe.name)
    return commands


def check_installed_command(command):
    """Check if a command is correctly installed"""
    config = get_config()
    if config is not None:
        venv_bin_dir = Path(config['venv_bin_dir'])
        executable = venv_bin_dir / command
        if not (executable.is_file() and os.access(executable, os.X_OK)):
            raise BoxError("command {} not installed".format(command))


def check_wrap_info(wrap_info):
    commands = []
    if wrap_info.wrap_mode is WrapMode.SINGLE:
        commands.append(wrap_info.wraps)
    elif wrap_info.wrap_mode is WrapMode.MULTIPLE:
        commands.extend(wrap_info.wraps.values())
    for command in commands:
        check_installed_command(command)


@functools.singledispatch
def tojson(obj):
    raise TypeError(obj)

@tojson.register(str)
@tojson.register(bool)
@tojson.register(int)
@tojson.register(float)
@tojson.register(type(None))
def _(obj):
    return obj


@tojson.register(Path)
def _(obj):
    return str(obj)


@tojson.register(collections.abc.Sequence)
def _(obj):
    return [tojson(value) for value in obj]


@tojson.register(collections.abc.Mapping)
def _(obj):
    return {tojson(key): tojson(value) for key, value in obj.items()}


@tojson.register(enum.Enum)
def _(obj):
    return obj.name


def create_header(state, fill_len=None):
    """Create the box-file header"""
    header = '''\
#!{python_interpreter}

# WARNING: this is a bentobox-generated file - do not edit!

"""
{state_json}
"""
'''.format(python_interpreter=state['python_interpreter'],
           state_json=json.dumps(tojson(state), indent=4))
    if fill_len:
        header += filler(fill_len)
    return header


def get_repo():
    """Return the repo"""
    return STATE['repo']


def _fmt_command(command):
    if command.name == command.command:
        return command.name
    else:
        return command.name + ":" + command.command


def get_box_type(state=STATE):
    wrap_mode = state['wrap_mode']
    if wrap_mode is WrapMode.SINGLE:
        return 'wraps({})'.format(tojson(state['wraps']))
    elif wrap_mode is WrapMode.MULTIPLE:
        return 'wraps({})'.format('|'.join(tojson(value) for value in state['wraps']))
    else:
        return 'installer'


################################################################################
### utils ######################################################################
################################################################################

class Output:
    """Output context manager"""
    def __init__(self, header=HEADER, verbose_level=None):
        verbose_level = get_verbose_level(verbose_level)
        self._header = header
        self._prev_line = None
        self._verbose_level = verbose_level
        if self._verbose_level > 0:
            self._file = sys.stderr
            self._persistent = self._verbose_level >= 2 or not self._file.isatty()
            self._columns = None
            if not self._persistent:
                with contextlib.suppress(OSError):
                    self._columns, _ = os.get_terminal_size()
        else:
            self._file = io.StringIO()
            self._persistent = True
            self._columns = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tback):
        self.clear()

    def clear(self):
        """Clear the last printed line"""
        if self._prev_line and not self._persistent:
            self._file.write('\r' + (' ' * len(self._prev_line)) + '\r')
            self._file.flush()
        self._prev_line = None

    def __call__(self, text):
        persistent = self._persistent
        columns = self._columns
        for text_line in text.split('\n'):
            line = self._header + text_line
            if persistent:
                self._file.write(line + '\n')
                self._prev_line = None
            else:
                self.clear()
                if columns is not None:
                    line = line[:columns]
                self._file.write(line)
                self._prev_line = line
            self._file.flush()

    def run_command(self, cmdline, *args, raising=True, **kwargs):
        persistent = self._persistent
        verbose_level = self._verbose_level
        result = subprocess.run(cmdline, *args, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, check=False, **kwargs)
        clist = [cmdline[0]] + [shlex.quote(arg) for arg in cmdline[1:]]
        cmd = " ".join(clist)
        kwargs = {}
        if persistent:
            self("$ " + cmd)
            if verbose_level > 2 or result.returncode:
                self(str(result.stdout, 'utf-8'), **kwargs)
        if result.returncode and raising:
            raise BoxError("command {} failed [{}]".format(cmd, result.returncode))
        return result.returncode


@contextlib.contextmanager
def set_install_dir(install_dir):
    """Context manager to locally change install dir"""
    current_install_dir = STATE['install_dir']
    try:
        STATE['install_dir'] = str(Path(install_dir).resolve())
        yield
    finally:
        STATE['install_dir'] = current_install_dir


@contextlib.contextmanager
def set_write_mode(filename):
    """Context manager to locally add write mode to a file"""
    filename = Path(filename)
    old_mode = filename.stat().st_mode
    new_mode = old_mode | 0o200
    try:
        filename.chmod(new_mode)
        yield
    finally:
        if filename.exists():
            filename.chmod(old_mode)


Lock = collections.namedtuple(  # pylint: disable=invalid-name
    "Lock", "path")


@contextlib.contextmanager
def lockfile(lock=None):
    """Lock file contex tmanager"""
    logfn = LOG.debug
    if lock is not None:
        yield lock
        return
    install_dir = get_install_dir()
    if not install_dir.exists():
        install_dir.mkdir(parents=True)
    lockpath = install_dir.joinpath("." + install_dir.name + ".bentobox.lock")
    pid = os.getpid()
    fhandle = open(lockpath, 'w+')
    try:
        logfn("waiting for lock %s...", lockpath)
        fcntl.lockf(fhandle.fileno(), fcntl.LOCK_EX)
        logfn("lock %s acquired", lockpath)
        fhandle.write("{}\n".format(pid))
        yield Lock(path=lockpath)
    finally:
        fcntl.lockf(fhandle.fileno(), fcntl.LOCK_UN)
        logfn("lock %s released", lockpath)
        fhandle.close()
        if lockpath.exists():
            logfn("removing lock %s", lockpath)
            lockpath.unlink()
        else:
            logfn("lock %s has gone!", lockpath)


def get_header_len(output_path):
    """Get the header length"""
    header_len = 0
    with open(output_path, "r") as output_file:
        for line in output_file:
            if line.startswith(MARK_END_OF_HEADER):
                break
            header_len += len(line)
    return header_len


def filler(fill_len, line_len=80):
    """Get fill lines"""
    if fill_len > 0:
        num_lines, rem = divmod(fill_len, line_len + 1)
        lines = []
        if num_lines:
            fill_line = "#" * line_len
            lines.extend(fill_line for _ in range(num_lines))
        if rem:
            lines.append("#" * (rem - 1))
        return '\n'.join(lines) + '\n'
    else:
        return ''


def replace_state(output_path, state):
    """Replace the box state"""
    output_path = Path(output_path)
    header = create_header(state)
    in_place = False
    if output_path.exists():
        old_header_len = get_header_len(output_path)
        if old_header_len >= len(header):
            in_place = True
            fill_len = old_header_len - len(header)
            fill = filler(fill_len)
            header += fill
            assert len(header) == old_header_len

    if in_place:
        with set_write_mode(output_path), open(output_path, "r+") as output_file:
            output_file.write(header)
    else:
        header += filler(fill_len=HEADER_FILL_LEN)
        if not output_path.exists():
            if not output_path.parent.is_dir():
                output_path.parents.mkdir(parents=True)
            shutil.copy(__file__, output_path)
        with set_write_mode(output_path):
            output_path_swp = output_path.with_name(output_path.name + ".swp")
            if not output_path_swp.parent.is_dir():
                output_path_swp.mkdir(parents=True)
            try:
                with open(output_path_swp, "w") as target_file, \
                     open(output_path, "r") as source_file:
                    target_file.write(header)
                    status = 'skip'
                    for line in source_file:
                        if status == 'skip':
                            if line.startswith(MARK_END_OF_HEADER):
                                target_file.write(line)
                                status = 'copy'
                        else:
                            target_file.write(line)
            except:  # pylint: disable=bare-except
                if output_path_swp.exists():
                    output_path_swp.unlink()
            else:
                if output_path_swp.exists():
                    output_path_swp.rename(output_path)


def _update_box_header(output, python_interpreter):
    """Update the box header in place"""
    if not UPDATE_SHEBANG:
        return
    if STATE['python_interpreter'] == python_interpreter:
        return
    output("replacing shebang...")
    state = STATE.copy()
    if not state['python_interpreter_orig']:
        state['python_interpreter_orig'] = state['python_interpreter']
    state['python_interpreter'] = python_interpreter
    replace_state(__file__, state)


def _reset_box_header(output):
    """Reset the box header in place"""
    if not UPDATE_SHEBANG:
        return
    if STATE['python_interpreter_orig'] is None:
        return
    output("resetting shebang...")
    state = STATE.copy()
    state['python_interpreter'] = state['python_interpreter_orig']
    state['python_interpreter_orig'] = None
    replace_state(__file__, state)


def configure(output_path, install_dir=UNDEFINED, wrap_info=UNDEFINED,
              verbose_level=UNDEFINED, freeze=UNDEFINED,
              update_shebang=UNDEFINED):
    """Change the STATE and update the file if necessary"""
    state = STATE.copy()
    if install_dir is not UNDEFINED:
        if install_dir is not None:
            install_dir = Path(install_dir).resolve()
        state['install_dir'] = install_dir
    if wrap_info is not UNDEFINED:
        check_wrap_info(wrap_info)
        state['wrap_mode'] = wrap_info.wrap_mode
        state['wraps'] = wrap_info.wraps
    if verbose_level is not UNDEFINED:
        state['verbose_level'] = verbose_level
    if freeze is not UNDEFINED:
        state['freeze'] = freeze
    if update_shebang is not UNDEFINED:
        state['update_shebang'] = update_shebang
    replace_state(output_path, state)


def uninstall(verbose_level=None):
    verbose_level = get_verbose_level(verbose_level)
    install_dir = get_install_dir()
    with Output(verbose_level=verbose_level) as output:
        with lockfile():
            shutil.rmtree(install_dir, ignore_errors=True)
        _reset_box_header(output)


def install(env_file=None, reinstall=None, verbose_level=None, update_shebang=None):
    """Install the box, if needed"""
    if update_shebang is None:
        update_shebang = UPDATE_SHEBANG

    install_dir = get_install_dir()

    repo_dir = install_dir / "repo"
    bentobox_config_file = install_dir / "bentobox-config.json"
    bentobox_env_file = install_dir / "bentobox-env.sh"

    with Output(verbose_level=verbose_level) as output:
        with lockfile():

            if env_file is None:
                source_file = bentobox_env_file.resolve()
            else:
                env_file = env_file.resolve()
                source_file = env_file

            venv_dir = install_dir / "venv"
            venv_bin_dir = venv_dir / "bin"
            config = {
                'version': VERSION,
                'box_file_version': STATE['box_file_version'],
                'install_dir': install_dir,
                'env_file': env_file,
                'source_file': source_file,
                'venv_dir': venv_dir,
                'venv_bin_dir': venv_bin_dir,
                'pip_install_args': STATE['pip_install_args'],
                'packages': STATE['packages'],
            }

            do_install = True
            installed_config = get_config()
            if installed_config is not None:
                if reinstall:
                    LOG.warning("reinstalling box %s...", STATE['box_name'])
                    do_install = True
                else:
                    installed_box_file_version = installed_config.get('box_file_version', 0)
                    if installed_box_file_version != STATE['box_file_version']:
                        raise BoxFileVersionMismatch(
                            "installed version: {} current version: {}".format(
                                installed_box_file_version,
                                STATE['box_file_version']))
                    installed_packages = installed_config['packages']
                    configured_packages = STATE['packages']
                    num_common_packages = 0
                    for pkg1, pkg2 in zip(installed_packages, configured_packages):
                        if pkg1 != pkg2:
                            break
                        num_common_packages += 1
                    if STATE['packages'] != installed_config['packages']:
                        for ptype, packages in [('installed', installed_config['packages']),
                                                ('configured', STATE['packages'])]:
                            LOG.debug("%s packages:", ptype)
                            for idx, pkg in enumerate(packages):
                                if idx < num_common_packages:
                                    pre = '='
                                else:
                                    pre = '!'
                                LOG.debug("  %s %s", pre, pkg)
                        if reinstall is None:
                            LOG.warning("already installed, but reinstall is needed")
                            do_install = True
                        else:
                            LOG.error("already installed, but reinstall is needed")
                            return None
                    else:
                        do_install = False

            if do_install:
                def freeze_python(output, venv_bin_dir, python_name):
                    python_exe = venv_bin_dir / python_name
                    if python_exe.exists():
                        output("freezing python {}...".format(python_name))
                        if python_exe.is_symlink():
                            python_actual_exe = python_exe.resolve()
                            python_exe.unlink()
                        else:
                            python_actual_exe = venv_bin_dir / ("bentobox-" + python_name)
                            python_exe.rename(python_actual_exe)
                        python_wrapper_source = """\
#!/bin/bash

export LD_LIBRARY_PATH="${{LD_LIBRARY_PATH}}:{python_libs}"
exec {python_exe} "$@"
""".format(python_exe=python_actual_exe, python_libs=os.environ.get('LD_LIBRARY_PATH', ''))
                        with open(python_exe, "w") as fhandle:
                            fhandle.write(python_wrapper_source)
                        python_exe.chmod(python_actual_exe.stat().st_mode)
                        return python_exe
                    return None

                try:
                    if bentobox_config_file.exists():
                        output("removing install dir {}...".format(install_dir))
                        shutil.rmtree(install_dir, ignore_errors=True)

                    if not repo_dir.is_dir():
                        repo_dir.mkdir(parents=True)

                    pypi_dir = _extract(output, None, repo_dir)

                    output("creating venv {}...".format(venv_dir))
                    venv.create(venv_dir, with_pip=True)
                    if FREEZE:
                        for python_name in 'python3', 'python':
                            freeze_python(output, venv_bin_dir, python_name)

                    pip_path = venv_bin_dir / "pip"

                    environ = get_environ(config)

                    if STATE['use_pypi']:
                        pip_index_options = ["--extra-index-url", "file://" + str(pypi_dir)]
                    else:
                        pip_index_options = ["--index-url", "file://" + str(pypi_dir)]

                    output("initializing venv...")
                    pip_cmdline = [str(pip_path), "install", "--upgrade"]
                    pip_cmdline += pip_index_options
                    pip_cmdline += STATE['init_venv_packages']
                    output.run_command(pip_cmdline, env=environ)

                    output("installing packages...")
                    pip_cmdline = [str(pip_path), "install"]
                    pip_cmdline.extend(str(arg) for arg in STATE['pip_install_args'])
                    pip_cmdline += pip_index_options
                    pip_cmdline += STATE['packages']
                    output.run_command(pip_cmdline, env=environ)

                    base_commands = set(find_executables(venv_bin_dir))
                    installed_commands = set(find_executables(venv_bin_dir)) - base_commands
                    config["installed_commands"] = sorted(installed_commands)

                    output("creating activate file {}...".format(bentobox_env_file))
                    with open(bentobox_env_file, "w") as fhandle:
                        fhandle.write("""\
# environmen    t for box {box_name}
# automatically created by bentobox

export PATH="${{PATH}}:{venv_bin_dir}"
""".format(venv_bin_dir=venv_bin_dir, **STATE))
                    output("creating config file {}...".format(bentobox_config_file))
                    with open(bentobox_config_file, "w") as fhandle:
                        print(json.dumps(tojson(config), indent=4, sort_keys=True), file=fhandle)
                except:  # pylint: disable=bare-except
                    shutil.rmtree(install_dir, ignore_errors=True)
                    raise

        if env_file:
            output("copying env file to {}...".format(env_file))
            if not env_file.parent.is_dir():
                env_file.parent.mkdir(parents=True)
            shutil.copyfile(bentobox_env_file, env_file)

        if update_shebang:
            python_interpreter = sys.executable
            for python_name in 'python3', 'python':
                python_exe = venv_bin_dir / python_name
                if python_exe.is_file():
                    python_interpreter = python_exe
                    break
            _update_box_header(output, str(python_interpreter))

    if not do_install:
        config = get_config()
    return do_install, config


################################################################################
### exported functions #########################################################
################################################################################

MAIN_INDEX_SOURCE = """\
<!DOCTYPE html>
<html>
  <head>
    <title>
      Simple Index
    </title>
    <meta name='api-version' value='2' />
  </head>
  <body>
{content}
  </body>
</html>
"""

PACKAGE_REF_SOURCE = '''    <a href="{package_name}/">{package_name}</a>'''


PACKAGE_INDEX_SOURCE = """\
<!DOCTYPE html>
<html>
  <body>
    <a href="{package_filename}">{package_filename}</a><br />
  </body>
</html>
"""


def build_pypi_simple(repo_dir, package_data, pypi_dir=None):
    repo_dir = Path(repo_dir).resolve()
    if pypi_dir is None:
        pypi_dir = repo_dir / 'simple'
    shutil.rmtree(pypi_dir, ignore_errors=True)
    pypi_dir.mkdir(parents=True)
    pypi_index_path = pypi_dir / 'index.html'
    content = []
    for package_name, package_filename, _ in package_data:
        content.append(PACKAGE_REF_SOURCE.format(package_name=package_name))
        package_path = repo_dir / package_filename
        package_dir = pypi_dir / package_name
        if not package_dir.is_dir():
            package_dir.mkdir(parents=True)
        package_link_path = package_dir / package_path.name
        package_link_path.symlink_to(Path("..") / ".." / package_path.name)
        package_index_path = package_dir / 'index.html'
        with open(package_index_path, "w") as package_index_file:
            package_index_file.write(
                PACKAGE_INDEX_SOURCE.format(package_filename=package_filename)
            )
    with open(pypi_index_path, "w") as pypi_index_file:
        pypi_index_file.write(MAIN_INDEX_SOURCE.format(
            content='\n'.join(content)
        ))
    return pypi_dir


def _extract(output, hashlist, output_dir):
    """Implementation of the extract function"""
    if not output_dir.is_dir():
        output("creating output dir {}...".format(output_dir))
        output_dir.mkdir()
    output("reading repo packages from {}...".format(__file__))
    package_data = []
    package_filename = None
    package_name = None
    package_hash = None
    package_file = None
    if hashlist is None:
        hashlist = []
        for package_dct in get_repo().values():
            for package_hash in package_dct.values():
                hashlist.append(package_hash)
    hashset = set(hashlist)
    try:
        with open(__file__, "r") as source_file:
            for line in source_file:
                if line.startswith(MARK_REPO):
                    break
            status = 'package-name'
            for line in source_file:
                src = line[1:-1]
                if not src:
                    status = 'package-name'
                    continue
                if status == 'package-name':
                    package_name = src
                    status = 'package-filename'
                elif status == 'package-filename':
                    package_filename = src
                    status = 'package-hash'
                elif status == 'package-hash':
                    package_hash = src
                    if package_hash in hashset:
                        if package_file:
                            package_file.close()
                        package_path = output_dir / package_filename
                        if not package_path.parent.is_dir():
                            package_path.parent.mkdir(parents=True)
                        package_data.append((package_name, package_filename, package_hash))
                        output("extracting package {} [{}]...".format(
                            package_filename, package_hash))
                        package_file = open(package_path, 'wb')
                        status = 'package-data'
                    else:
                        status = 'skip'
                elif status == 'package-data':
                    data = b64decode(src)
                    package_file.write(data)
                elif status == 'skip':
                    pass
    finally:
        if package_file:
            package_file.close()
    return build_pypi_simple(output_dir, package_data)


def extract(hashlist, output_dir=None, verbose_level=None):
    """Extract packages with given hash"""
    if output_dir is None:
        output_dir = get_install_dir() / 'boxes'
    with Output(verbose_level=verbose_level) as output:
        return _extract(output, hashlist, output_dir)


def check(install_dir=None):
    """Verify the box"""
    if install_dir is None:
        with tempfile.TemporaryDirectory() as tmpd:
            check(Path(tmpd) / "bentobox_install_dir")
            return
    with set_install_dir(install_dir):
        install(update_shebang=False)
        wrap_info = get_wrap_info()
        check_wrap_info(wrap_info)


def show(mode='text'):
    """Show command"""
    if mode == 'json':
        print(json.dumps(tojson(STATE), indent=4))
    else:
        if STATE['install_dir'] is None:
            actual_install_dir = " [{}]".format(get_install_dir())
        else:
            actual_install_dir = ""
        box_type = get_box_type(STATE)
        print("""\
Box: {box_name} [{box_type}]
  + install_dir = {install_dir}{actual_install_dir}
  + wrap_mode = {wrap_mode}
  + wraps = {wraps}
  + pip_install_args = {pip_install_args}
  + update_shebang = {update_shebang}
  + packages:""".format(actual_install_dir=actual_install_dir, box_type=box_type, **STATE))
        for package_name in STATE['packages']:
            print("    + {}".format(package_name))
        print("""\
  + repo:""")
        for package_name, package_data in STATE['repo'].items():
            print("    + {}".format(package_name))
            for package_path, package_hash in package_data.items():
                print("      + {}: {}".format(package_hash, package_path))


################################################################################
### parser commands ############################################################
################################################################################

def cmd_configure(output_path, install_dir, wrap_info=UNDEFINED, update_shebang=UNDEFINED,
                  verbose_level=UNDEFINED, freeze=UNDEFINED):
    """Configure command"""
    return configure(output_path, install_dir, wrap_info=wrap_info,
                     verbose_level=verbose_level,
                     update_shebang=update_shebang, freeze=freeze)


def cmd_extract(hashlist, output_dir=None, verbose_level=None):
    """Extract command"""
    verbose_level = get_verbose_level(verbose_level)
    extract(
        output_dir=output_dir,
        hashlist=hashlist,
        verbose_level=verbose_level)


def cmd_install(env_file, reinstall=False, update_shebang=None, verbose_level=None):
    """Install command"""
    verbose_level = get_verbose_level(verbose_level)
    reinstalled, config = install(
        env_file=env_file,
        reinstall=reinstall,
        update_shebang=update_shebang,
        verbose_level=verbose_level)

    if config is None:
        return 1

    if reinstalled:
        print("""\
################################################################################
Box {box_name!r} has been installed.
################################################################################
""".format(**STATE))
    else:
        print("""\
################################################################################
Box {box_name!r} already installed.
################################################################################
""".format(**STATE))
    print("""\
The install dir is:
  {install_dir}

To activate the installation run:
  source {source_file}
""".format(
        install_dir=config['install_dir'],
        source_file=config['source_file']))

    sys.exit(0)


def cmd_uninstall(verbose_level=None):
    """Uninstall command"""
    uninstall(verbose_level=verbose_level)


def cmd_show(mode='text'):
    """Show command"""
    show(mode=mode)


def cmd_list(what='commands'):
    """List command"""
    if what == 'commands':
        config = get_config()
        if config is None:
            raise ValueError("cannot list commands: box not installed")
        for command in sorted(find_executables(config["venv_bin_dir"])):
            print(command)
    elif what == 'packages':
        for package_name in STATE['packages']:
            print(package_name)
    elif what == 'repo':
        for package_name, package_data in STATE['repo'].items():
            print(package_name)
            for package_filename, package_hash in package_data.items():
                print("  {}: {}".format(package_hash, package_filename))
    elif what == 'environment':
        for var_info in ENV_VARS.values():
            if not var_info.description:
                continue
            dct = var_info._asdict()
            var_type = dct['var_type']
            dct['var_type_name'] = getattr(var_type, '__name__', str(var_type))
            print("""\
{var_name}: {description}
  - type:    {var_type_name}
  - value:   {var_value!r}
  - default: {default!r}""".format(**dct))


def cmd_run(command, args, verbose_level=None, reinstall=False):
    """Run command"""
    verbose_level = get_verbose_level(verbose_level)
    _, config = install(verbose_level=verbose_level, reinstall=reinstall)
    if config is None:
        return 1

    executable = Path(config['venv_bin_dir']) / command
    if not executable.is_file():
        LOG.error("missing executable %s", executable)
        return 1
    if not os.access(executable, os.X_OK):
        LOG.error("not an executable: %s", executable)
        return 1
    environ = get_environ(config)
    executable = str(executable)
    cmdline = [executable] + list(args)
    return os.execve(executable, cmdline, environ)


################################################################################
### argument parsing ###########################################################
################################################################################

def add_common_arguments(parser):
    default_verbose_level = get_verbose_level()
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


def add_reinstall_argument(parser):
    parser.add_argument(
        "-r", "--reinstall",
        action="store_true", default=False,
        help="force reinstall if already installed")


def add_configure_parser(subparsers):
    parser = subparsers.add_parser(
        "configure",
        description="""\
Box {box_name!r} - configure box script
""".format(**STATE))
    parser.set_defaults(
        function=cmd_configure,
        function_args=['install_dir', 'output_path', 'wrap_info', 'verbose_level',
                       'freeze', 'update_shebang'],
    )
    add_common_arguments(parser)

    parser.add_argument(
        "-F", "--no-freeze",
        dest="freeze", default=UNDEFINED,
        action="store_false",
        help="do not freeze virtualenv")

    parser.add_argument(
        "-U", "--no-update-shebang",
        dest="update_shebang", default=UNDEFINED,
        action="store_false",
        help="do not update shebang")

    install_dir_group = parser.add_argument_group("install_dir")
    install_dir_mgrp = install_dir_group.add_mutually_exclusive_group()
    install_dir_kwargs = {'dest': 'install_dir', 'default': UNDEFINED}
    install_dir_mgrp.add_argument(
        "-I", "--install-dir",
        type=Path,
        help="set install dir",
        **install_dir_kwargs)
    install_dir_mgrp.add_argument(
        "-P", "--unset-install-dir",
        action="store_const", const=None,
        help="unset install dir",
        **install_dir_kwargs)

    wrap_info_group = parser.add_argument_group("wrapping")
    wrap_info_mgrp = wrap_info_group.add_mutually_exclusive_group()
    wrap_info_kwargs = {'dest': 'wrap_info', 'default': UNDEFINED}
    wrap_info_mgrp.add_argument(
        "-w", "--wrap-command",
        metavar="COMMAND",
        help="wrap a single installed COMMAND",
        type=wrap_single,
        **wrap_info_kwargs)
    wrap_info_mgrp.add_argument(
        "-W", "--wrap-commands",
        metavar="CMD1[,CMD2[...]]",
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

    output_group = parser.add_argument_group("output")
    output_mgrp = output_group.add_mutually_exclusive_group(required=True)
    output_mgrp.add_argument(
        "-o", "--output-path",
        dest="output_path",
        type=Path,
        help="output path")
    output_mgrp.add_argument(
        "-i", "--in-place",
        dest="output_path",
        action="store_const", const=Path(__file__),
        help="change the box in-place")
    return parser


def add_list_parser(subparsers):
    parser = subparsers.add_parser(
        "list",
        description="""\
Box {box_name!r} - list available commands
""".format(**STATE))
    parser.set_defaults(
        function=cmd_list,
        function_args=['what'],
    )
    what_mgrp = parser.add_mutually_exclusive_group()
    what_kwargs = {'dest': 'what', 'default': 'commands'}
    what_mgrp.add_argument(
        "-c", "--commands",
        action="store_const", const="commands",
        help="list installed commands",
        **what_kwargs)
    what_mgrp.add_argument(
        "-p", "--packages",
        action="store_const", const="packages",
        help="list packages",
        **what_kwargs)
    what_mgrp.add_argument(
        "-r", "--repo",
        action="store_const", const="repo",
        help="list repo content",
        **what_kwargs)
    what_mgrp.add_argument(
        "-e", "--environment",
        action="store_const", const="environment",
        help="list bentobox environment variables",
        **what_kwargs)
    return parser


def add_run_parser(subparsers):
    parser = subparsers.add_parser(
        "run",
        description="""\
Box {box_name!r} - run installed command
""".format(**STATE))
    parser.set_defaults(
        function=cmd_run,
        function_args=['command', 'args', 'verbose_level', 'reinstall'],
    )
    add_common_arguments(parser)
    add_reinstall_argument(parser)
    parser.add_argument(
        "command",
        help="command name")
    parser.add_argument(
        "args",
        nargs='*',
        help="command arguments")
    return parser


def add_extract_parser(subparsers):
    def package_hash(value):
        matching_entries = []
        for package_name, package_data in get_repo().items():
            for package_filename, package_hash in package_data.items():
                if (package_filename == value or package_name == value or
                        package_hash.startswith(value)):
                    matching_entries.append(package_hash)
        if len(matching_entries) == 1:
            return matching_entries[0]
        else:
            raise ValueError(value)

    parser = subparsers.add_parser(
        "extract",
        description="""\
Box {box_name!r} - extract packages and create a PyPI repo
""".format(**STATE))
    parser.set_defaults(
        function=cmd_extract,
        function_args=['output_dir', 'hashlist', 'verbose_level'],
    )
    add_common_arguments(parser)
    parser.add_argument(
        "-O", "--output-dir",
        type=Path,
        default=None,
        help="output dir")
    hashlist_group = parser.add_argument_group("packages")
    hashlist_mgrp = hashlist_group.add_mutually_exclusive_group(required=True)
    hashlist_kwargs = {'dest': 'hashlist', 'default': []}
    hashlist_mgrp.add_argument(
        "-p", "--package",
        type=package_hash,
        action="append",
        help="package name or hash",
        **hashlist_kwargs)
    hashlist_mgrp.add_argument(
        "-A", "--all",
        action="store_const", const=None,
        help="extract all packages",
        **hashlist_kwargs)
    return parser


def add_install_parser(subparsers):
    parser = subparsers.add_parser(
        "install",
        description="""\
Box {box_name!r} - install box
""".format(**STATE))
    parser.set_defaults(
        function=cmd_install,
        function_args=['env_file', 'reinstall', 'verbose_level', 'update_shebang'],
    )
    add_common_arguments(parser)
    add_reinstall_argument(parser)
    freeze_group = parser.add_argument_group("freeze")
    freeze_mgrp = freeze_group.add_mutually_exclusive_group()
    freeze_kwargs = {'dest': 'freeze', 'default': STATE.get('freeze', None)}
    freeze_mgrp.add_argument(
        "-f", "--freeze",
        action="store_true",
        help="freeze virtualenv",
        **freeze_kwargs)
    freeze_mgrp.add_argument(
        "-F", "--no-freeze",
        action="store_false",
        help="do not freeze virtualenv",
        **freeze_kwargs)

    update_shebang_group = parser.add_argument_group("shebang")
    update_shebang_mgrp = update_shebang_group.add_mutually_exclusive_group()
    update_shebang_kwargs = {'dest': 'update_shebang', 'default': STATE.get('update_shebang', None)}
    update_shebang_mgrp.add_argument(
        "-s", "--shebang-update",
        action="store_true",
        help="update shebang when installing",
        **update_shebang_kwargs)
    update_shebang_mgrp.add_argument(
        "-S", "--no-shebang-update",
        action="store_false",
        help="do not update shebang when installing",
        **update_shebang_kwargs)

    parser.add_argument(
        "-e", "--env-file",
        type=Path, default=None,
        help="write env file")
    return parser


def add_uninstall_parser(subparsers):
    parser = subparsers.add_parser(
        "uninstall",
        description="""\
Box {box_name!r} - uninstall box
""".format(**STATE))
    parser.set_defaults(
        function=cmd_uninstall,
        function_args=['verbose_level'],
    )
    add_common_arguments(parser)
    return parser


def add_show_parser(subparsers):
    parser = subparsers.add_parser(
        "show",
        description="""\
Box {box_name!r} - show box state
""".format(**STATE))
    parser.set_defaults(
        function=cmd_show,
        function_args=["mode"],
    )
    add_common_arguments(parser)
    mode_group = parser.add_argument_group("mode")
    mode_mgrp = mode_group.add_mutually_exclusive_group()
    default_mode = "text"
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
    return parser


################################################################################
### main #######################################################################
################################################################################

def main(args=None):
    try:
        if args is None:
            args = sys.argv[1:]

        if FORCE_REINSTALL or UNINSTALL:
            config = get_config()
            if config is None:
                LOG.debug("%r is not installed", STATE['box_name'])
            else:
                uninstall()
                LOG.debug("%r has been successfully uninstalled", STATE['box_name'])
            if FORCE_REINSTALL:
                if config is not None:
                    executable = __file__
                    cmdline = [executable] + list(args)
                    environ = get_environ(config)
                    environ.pop('BBOX_FORCE_REINSTALL', None)
                    return os.execve(executable, cmdline, environ)
            else:
                if args:
                    LOG.warning("command line arguments ignored: %s",
                                " ".join(shlex.quote(arg) for arg in args))
                sys.exit(0)

        wrap_info = get_wrap_info()
        if wrap_info.wrap_mode is WrapMode.SINGLE:
            return main_wrap_single(wrap_info.wraps, args)
        elif wrap_info.wrap_mode is WrapMode.MULTIPLE:
            return main_wrap_multiple(wrap_info.wraps, args)
        elif wrap_info.wrap_mode is WrapMode.ALL:
            return main_wrap_multiple(None, args)
        else:
            return main_box(args)
    except Exception as err:  # pylint: disable=broad-except
        if VERBOSE_LEVEL >= DEBUG_LEVEL:
            LOG.exception("exception found:")
        else:
            LOG.error("%s: %s", type(err).__name__, err)


def main_box(args=None):
    parser = argparse.ArgumentParser(
        description="""\
Box {box_name} - manage box
""".format(**STATE)
    )
    parser.set_defaults(
        function=parser.print_help,
        function_args=[])
    parser.add_argument(
        "-t", "--trace",
        action="store_true", default=False,
        help=argparse.SUPPRESS)

    subparsers = parser.add_subparsers()

    add_show_parser(subparsers)
    add_configure_parser(subparsers)
    add_extract_parser(subparsers)
    add_install_parser(subparsers)
    add_uninstall_parser(subparsers)
    add_list_parser(subparsers)
    add_run_parser(subparsers)

    namespace = parser.parse_args(args)
    verbose_level = getattr(namespace, 'verbose_level', None)
    trace = getattr(namespace, 'trace', False)
    function = namespace.function
    kwargs = {arg: getattr(namespace, arg) for arg in namespace.function_args}

    configure_logging(verbose_level=verbose_level)
    try:
        return function(**kwargs)
    except Exception as err:  # pylint: disable=broad-except
        if trace:
            traceback.print_exc()
        print("ERR: {}".format(err), file=sys.stderr)
        return 2


def main_wrap_single(command, args):
    _, config = install(reinstall=None)
    if config is None:
        return 1
    return _wrap_command(config, command, args)


def main_wrap_multiple(commands, args):
    _, config = install(reinstall=None)
    if config is None:
        return 1
    if commands is None:
        commands = {name: name for name in config["installed_commands"]}
    c_args, a_args = args[:1], args[1:]
    parser = argparse.ArgumentParser(description=STATE['box_name'])
    parser.add_argument(
        "command",
        choices=sorted(commands),
    )
    namespace = parser.parse_args(c_args)
    command = commands[namespace.command]
    return _wrap_command(config, command, a_args)


def _wrap_command(config, command, args):
    installed_commands = find_executables(config['venv_bin_dir'])

    if command not in installed_commands:
        LOG.error("missing command %s", command)
        print("""\

################################################################################
  This box is configured to wrap the command
     {command}

  Anyway, this command is not installed.

  Available commands are:
""".format(command=command))
        print(textwrap.fill(" ".join(sorted(installed_commands)),
                            initial_indent="    ",
                            subsequent_indent="    ",
                            break_long_words=False))
        print("""
  You can reconfigure the box with the following command:

      $ BBOX_WRAPPING=off {prog} configure --in-place -w COMMAND

  where COMMAND is any installed command
################################################################################
""".format(prog=sys.argv[0]))
        sys.exit(1)

    executable = str(Path(config['venv_bin_dir']) / command)
    cmdline = [executable] + list(args)
    environ = get_environ(config)
    return os.execve(executable, cmdline, environ)


if __name__ == "__main__":
    main()

# --- end-of-source ---
# --- repo ---
