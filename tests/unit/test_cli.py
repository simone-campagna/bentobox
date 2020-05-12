import shlex
import sys
import uuid

from pathlib import Path
from unittest import mock

import pytest

from bentobox import box_file as _box_file
from bentobox.cli import (
    function_create,
    function_show,
    main,
)
from bentobox.errors import (
    BoxPathError,
)


def mk_kwargs(argstring):
    args = [arg.strip() for arg in argstring.split(',')]
    print(args)
    return {arg: uuid.uuid4() for arg in args}


def test_function_create():
    kwargs = mk_kwargs("""box_name, wrap_info, output_path,
                          packages, update_shebang, check,
                          python_interpreter, force_overwrite,
                          verbose_level, pip_install_args,
                          freeze_env, freeze_pypi""")
    print(kwargs)
    create_box_file_mock = mock.MagicMock()
    with mock.patch("bentobox.cli.create_box_file", create_box_file_mock):
        function_create(**kwargs)
    box_name = kwargs.pop("box_name")
    assert create_box_file_mock.call_args == ((box_name,), kwargs)


def test_function_show(tmp_path):
    box_path = tmp_path / "mybox"
    box_mock = mock.MagicMock()
    load_py_mock = mock.MagicMock(return_value=box_mock)
    with mock.patch("bentobox.cli.load_py_module", load_py_mock):
        function_show(box_path, mode="json")
    assert load_py_mock.call_args == ((box_path,),)
    assert box_mock.show.call_args == ((), {'mode': 'json'})


@pytest.mark.parametrize("argstring, function, kwargs", [
    [
        "create -n mybox 'pkg_a>=2.1' 'pkg_b==2.3' -w myprog.x",
        function_create,
        {
            'box_name': 'mybox',
            'wrap_info': _box_file.WrapInfo(_box_file.WrapMode.SINGLE, 'myprog.x'),
            'packages': ['pkg_a>=2.1', 'pkg_b==2.3'],
            'check': True,
            'update_shebang': True,
            'freeze_env': True,
            'freeze_pypi': True,
            'force_overwrite': False,
            'pip_install_args': None,
            'verbose_level': _box_file.VERBOSE_LEVEL,
        }
    ],
    [
        "create -n mybox 'pkg_a>=2.1' 'pkg_b' -C -E -F -O -U -A -a=-a1 -a v1 -o xy.z -p /opt/pypy",
        function_create,
        {
            'box_name': 'mybox',
            'wrap_info': _box_file.WrapInfo(_box_file.WrapMode.ALL, None),
            'packages': ['pkg_a>=2.1', 'pkg_b'],
            'check': False,
            'update_shebang': False,
            'freeze_env': False,
            'freeze_pypi': False,
            'force_overwrite': True,
            'pip_install_args': ['-a1', 'v1'],
            'output_path': Path('xy.z'),
            'python_interpreter': '/opt/pypy',
        }
    ],
    [
        "create -n mybox 'pkg_a>=2.1' -W a.x,a.y,bx=b.x,by=b.y -P",
        function_create,
        {
            'box_name': 'mybox',
            'wrap_info': _box_file.WrapInfo(_box_file.WrapMode.MULTIPLE,
                                            {'a.x': 'a.x', 'a.y': 'a.y',
                                             'bx': 'b.x', 'by': 'b.y'}),
            'packages': ['pkg_a>=2.1'],
            'python_interpreter': sys.executable,
        }
    ],
    [
        "create -n mybox -N -vvvvv",
        function_create,
        {'verbose_level': 5}
    ],
    [
        "create -n mybox -N -V3",
        function_create,
        {'verbose_level': 3}
    ],
    [
        "create -n mybox -N -q",
        function_create,
        {'verbose_level': 0}
    ],
    ### show:
    [
        "show mybox.x",
        function_show,
        {'box_path': Path("mybox.x"), 'mode': 'json'}
    ],
    [
        "show mybox.x -t",
        function_show,
        {'box_path': Path("mybox.x"), 'mode': 'text'}
    ],
])
def test_main(argstring, function, kwargs):
    args = shlex.split(argstring)
    print(args)
    fname = function.__name__
    fmock = mock.MagicMock()
    with mock.patch("bentobox.cli.{}".format(fname), fmock), \
         mock.patch("sys.argv", ['bentobox'] + args):
        main()
    call_args, call_kwargs = fmock.call_args
    assert not call_args
    for key, val in kwargs.items():
        assert call_kwargs[key] == val


def equals(string):
    return lambda x: x == string

    
def has_substring(substring):
    return lambda x: substring in x


@pytest.mark.parametrize("argstring, function, exc_type, check_out, check_err", [
    ["create -n a.b", function_create, SystemExit,
     equals(""), has_substring("invalid t_box_name value: 'a.b'")],
    ["create -p python37", function_create, SystemExit,
     equals(""), has_substring("invalid t_python_exe value: 'python37'")],
])
def test_main_arg_errors(capsys, argstring, function, exc_type, check_out, check_err):
    args = shlex.split(argstring)
    fname = function.__name__
    fmock = mock.MagicMock()
    with mock.patch("bentobox.cli.{}".format(fname), fmock), \
         mock.patch("sys.argv", ['bentobox'] + args):
        with pytest.raises(exc_type) as exc_info:
            main()
    captured = capsys.readouterr()
    assert check_out(captured.out)
    assert check_err(captured.err)


def test_main_without_traceback(capsys):
    with mock.patch("sys.argv", ['bentobox', 'show', '/tmp/missing-filename']):
        result = main()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "BoxPathError:" in captured.err
    assert not "Traceback" in captured.err
    assert result == 2
    


def test_main_with_traceback(capsys):
    with mock.patch("sys.argv", ['bentobox', '-t', 'show', '/tmp/missing-filename']):
        result = main()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "BoxPathError:" in captured.err
    assert "Traceback" in captured.err
    assert result == 2
    

def test_main_result(capsys):
    with mock.patch("bentobox.cli.function_create", mock.MagicMock(return_value=None)), \
         mock.patch("sys.argv", ['bentobox', 'create', '-n', 'mybox', '-N']):
        result = main()
    assert result == 0
