import functools
import subprocess
import shlex
import sys
import tempfile

from pathlib import Path

from importlib.util import spec_from_file_location, module_from_spec

from .errors import BoxCommandError, BoxPathError

__all__ = [
    'load_py_module',
    'run_command',
]


def load_py_module(module_path):
    module_path = Path(module_path).resolve()
    if not module_path.is_file():
        raise BoxPathError(module_path)
    return _load_py_module(module_path)


@functools.lru_cache(maxsize=10)
def _load_py_module(module_path):
    with tempfile.TemporaryDirectory() as tmpd:
        module_name = module_path.name
        module_link = Path(tmpd) / (module_name + ".py")
        module_link.symlink_to(module_path)
        spec = spec_from_file_location(module_name, str(module_link))
        module = module_from_spec(spec)
        module.__file__ = str(module_path)
        spec.loader.exec_module(module)
        return module


def print_err(*args, file=None, **kwargs):
    if file is None:
        file = sys.stderr
    print(*args, file=file, **kwargs)


def run_command(cmdline, raising=True, print_function=print_err):
    result = subprocess.run(cmdline, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            check=False)
    if result.returncode:
        clist = [cmdline[0]] + [shlex.quote(arg) for arg in cmdline[1:]]
        cmd = " ".join(clist)
        if raising:
            print_function("$ {}".format(cmd))
            print_function(str(result.stdout, 'utf-8'))
            raise BoxCommandError("command {} failed".format(cmd))
        print_function("ERR: command {} failed:".format(cmd))
        print_function(str(result.stdout, 'utf-8'))
    return result.returncode
