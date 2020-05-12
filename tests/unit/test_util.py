import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from bentobox.errors import (
    BoxCommandError,
    BoxPathError,
)
from bentobox.util import (
    load_py_module,
    run_command,
    print_err,
)


def test_load_py_module():
    with tempfile.TemporaryDirectory() as tmpd:
        mod_path = Path(tmpd) / "mymod"
        with open(mod_path, "w") as fmod:
            fmod.write("""\
def foo(i, j):
    return i * j
""")
        mod = load_py_module(mod_path)
        assert mod.__name__ == "mymod"
        assert mod.foo(2, 4) == 8


def test_load_py_module_error():
    with tempfile.TemporaryDirectory() as tmpd:
        mod_path = Path(tmpd) / "mymod"
        with pytest.raises(BoxPathError) as exc_info:
            mod = load_py_module(mod_path)


def mk_cmd(cmdline):
    clist = [cmdline[0]] + [shlex.quote(arg) for arg in cmdline[1:]]
    return ' '.join(clist)


def mk_run_mock(cmdline, returncode, stdout, stderr=None, raising=False):
    kwargs = {}
    if raising and returncode:
        cmd = mk_cmd(cmdline)
        kwargs['side_effect'] = BoxCommandError("command {} failed".format(cmd))
    else:
        kwargs['return_value'] = subprocess.CompletedProcess(
            args=cmdline,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr)
    return mock.MagicMock(**kwargs)


@pytest.mark.parametrize("returncode, stdout, raising", [
    [0, b'ok', None],
    [0, b'ok', False],
    [0, b'ok', True],
    [2, b'ko', None],
    [2, b'ko', False],
    [2, b'ko', True],
])
def test_run_command(returncode, stdout, raising, capsys):
    cmdline = ["./alpha", "--arg1", "a z", "--arg2=20"]
    s_run = mk_run_mock(cmdline, returncode, stdout)
    kwargs = {}
    if raising is not None:
        kwargs['raising'] = raising
    else:
        raising = True  # default
    with mock.patch("subprocess.run", s_run):
        if returncode and raising:
            with pytest.raises(BoxCommandError) as exc_info:
                run_command(cmdline, **kwargs)
            expected_out = ""
            expected_err = """\
$ {}
{}
""".format(mk_cmd(cmdline), str(stdout, 'utf-8'))
        else:
            result = run_command(cmdline, **kwargs)
            assert s_run.call_count == 1
            assert s_run.call_args == (
                (cmdline,),
                {'stdout': subprocess.PIPE, 'stderr': subprocess.STDOUT, 'check': False},
            )
            assert result == returncode
            expected_out = ""
            if returncode:
                expected_err = """\
ERR: command {} failed:
{}
""".format(mk_cmd(cmdline), str(stdout, 'utf-8'))
            else:
                expected_err = ""
    captured = capsys.readouterr()
    assert captured.out == expected_out
    assert captured.err == expected_err  


@pytest.mark.parametrize("message, where", [
    ['to stdout', None],
    ['to stdout', 'out'],
    ['to stderr', 'err'],
])
def test_print_err(capsys, message, where):
    if where in {'err', None}:
        file = sys.stderr
        out = ''
        err = message + '\n'
    else:
        file = sys.stdout
        out = message + '\n'
        err = ''
    print_err(message, file=file)
    captured = capsys.readouterr()
    assert captured.out == out
    assert captured.err == err
