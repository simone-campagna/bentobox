import copy
import io
import json
import fcntl
import os
import shutil
import stat
import subprocess
import sys

from pathlib import Path
from unittest import mock

import pytest


from bentobox import box_file as _box_file
from bentobox.util import load_py_module


@pytest.mark.parametrize("var_name, var_value", [
    ["FILE_PATH", None],
    ["DEFAULT_INSTALL_ROOT_DIR", Path("~") / ".bentobox" / "boxes"],
    ["HEADER", "[BENTOBOX] "],
])
def test_VAR(var_name, var_value):
    assert getattr(_box_file, var_name) == var_value


@pytest.mark.parametrize("fname", [
    Path('f.txt'),
    Path('d0') / 'f.txt',
    Path('d1') / 'd2' / 'f.txt',
])
def test_make_parent_dir(tmp_path, fname):
    fpath = tmp_path / fname
    _box_file.make_parent_dir(fpath)
    assert not fpath.exists()
    assert fpath.parent.is_dir()


@pytest.mark.parametrize("pth0, mode0, pth1, mode1, same", [
    ['x.txt', None, 'y.txt', None, False],
    ['x.txt', None, 'x.txt', None, True],
    ['x.txt', None, 'a/x.txt', None, False],
    ['x.txt', 'create', 'y.txt', None, False],
    ['x.txt', 'create', 'x.txt', None, True],
    ['b/x.txt', 'create', 'c/x.txt', None, False],
    ['x.txt', 'create', 'y.txt', 'hardlink', True],
    ['x.txt', 'create', 'a/x.txt', 'hardlink', True],
    ['b/x.txt', 'create', 'c/y.txt', 'hardlink', True],
    ['x.txt', 'create', 'y.txt', 'symlink', True],
    ['x.txt', 'create', 'a/x.txt', 'symlink', True],
    ['b/x.txt', 'create', 'c/y.txt', 'symlink', True],
])
def test_same_path(tmp_path, pth0, mode0, pth1, mode1, same):
    pth0 = tmp_path / pth0
    pth1 = tmp_path / pth1
    if mode0 == 'create':
        _box_file.make_parent_dir(pth0)
        pth0.touch()
    if mode1 == 'create':
        _box_file.make_parent_dir(pth1)
        pth1.touch()
    elif mode1 == 'hardlink':
        _box_file.make_parent_dir(pth1)
        os.link(pth0, pth1)
    elif mode1 == 'symlink':
        _box_file.make_parent_dir(pth1)
        pth1.symlink_to(pth0)
    assert _box_file.same_path(pth0, pth1) == same


@pytest.mark.parametrize("kwargs, logging_level", [
    [{}, 'ERROR'],
    [{'verbose_level': 0}, 'ERROR'],
    [{'verbose_level': 1}, 'WARNING'],
    [{'verbose_level': 2}, 'INFO'],
    [{'verbose_level': 3}, 'DEBUG'],
    [{'verbose_level': 9}, 'DEBUG'],
])
def test_configure_logging(kwargs, logging_level):
    dc_mock = mock.MagicMock()
    with mock.patch("logging.config.dictConfig", dc_mock):
        _box_file.configure_logging(**kwargs)
    if dc_mock.call_count > 0:
        c_args, c_kwargs = dc_mock.call_args
        config = c_args[0]
        logger_config = config['loggers'][_box_file.__name__]
        assert logger_config['level'] == logging_level


@pytest.mark.parametrize("file_path, environ, var_name, var_type, default, description, value, is_set", [
    # without FILE_PATH:
    [None, {},
     'BBOX_TEST_VAR', int, None, 'test var', None, False,
    ],
    [None, {'BBOX_TEST_VAR': 10},
     'BBOX_TEST_VAR', int, None, 'test var', None, False,
    ],
    # with FILE_PATH:
    ['/x', {},
     'BBOX_TEST_VAR', int, 100, 'test var', 100, False,
    ],
    ['/x', {'BBOX_TEST_VAR': 123},
     'BBOX_TEST_VAR', int, 100, 'test var', 123, True,
    ],
    ['/x', {'BBOX_TEST_VAR': 'alpha'},
     'BBOX_TEST_VAR', int, 100, 'test var', 100, False,
    ],
])
def test_get_env_var(environ, file_path, var_name, var_type, default, description, value, is_set):
    env_vars = {}
    with mock.patch('os.environ', environ), \
         mock.patch('bentobox.box_file.FILE_PATH', file_path), \
         mock.patch('bentobox.box_file.ENV_VARS', env_vars):
        var_value = _box_file.get_env_var(var_name, var_type, default, description)
    assert var_value == value
    assert var_name in env_vars
    assert env_vars[var_name] == _box_file.VarInfo(
        var_name=var_name,
        is_set=is_set,
        var_type=var_type,
        var_value=var_value,
        default=default,
        description=description)


@pytest.mark.parametrize("init_value, value", [
    ['0', False],
    ['off', False],
    ['OFF', False],
    ['no', False],
    ['False', False],
    ['1', True],
    ['111', True],
    ['on', True],
    ['ON', True],
    ['yes', True],
    ['TRUE', True],
    ['alpha', ValueError("invalid literal for int() with base 10: 'alpha'")],
])
def test_boolean(init_value, value):
    if isinstance(value, Exception):
        with pytest.raises(type(value)) as exc_info:
            _box_file.boolean(init_value)
        assert str(exc_info.value) == str(value)
    else:
        assert _box_file.boolean(init_value) == value


def test_resolved_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert _box_file.resolved_path("x.txt") == tmp_path / "x.txt"
    assert _box_file.resolved_path("/x.txt") == Path("/x.txt")

@pytest.mark.parametrize("state", [
    None,
    {'box_name': "alpha-omega", 'box_version': "abc123"},
])
def test_default_install_dir(state):
    if state is None:
        state = _box_file.STATE
    print(state)
    value = _box_file.default_install_dir(state)
    assert value == _box_file.DEFAULT_INSTALL_ROOT_DIR / state['box_name'] / state['box_version']


@pytest.mark.parametrize("box_name, box_version, var_install_dir, state_install_dir, install_dir", [
    ["abc", '123', None, None, None],
    ["abc", '123', Path('/a'), None, Path('/a')],
    ["abc", '123', None, '/b', Path('/b')],
    ["abc", '123', Path('/a'), '/b', Path('/a')],
])
def test_get_install_dir(box_name, box_version, var_install_dir, state_install_dir, install_dir):
    state = _box_file.STATE.copy()
    state['install_dir'] = state_install_dir
    state['box_name'] = box_name
    state['box_version'] = box_version
    if install_dir is None:
        install_dir = _box_file.default_install_dir(state).expanduser()
    with mock.patch("bentobox.box_file.INSTALL_DIR", var_install_dir), \
         mock.patch("bentobox.box_file.STATE", state):
        assert _box_file.get_install_dir() == install_dir


def test_ConfigFile(tmp_path):
    install_dir = tmp_path / "install-dir"
    with mock.patch("bentobox.box_file.get_install_dir", mock.MagicMock(return_value=install_dir)):
        config_file = _box_file.ConfigFile()
        assert config_file.mode == "a+"
        assert not config_file.lock
        assert config_file.path == install_dir / "bentobox-config.json"


def is_locked(path):
    with open(path, 'a+') as fhandle:
        try:
            fcntl.flock(fhandle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            print("::: {} locked".format(path), fhandle.fileno())
            return True
        else:
            print("::: {} NOT locked".format(path), fhandle.fileno())
            return False

def is_locked(path):
    with open(path, 'a+') as fhandle:
        try:
            fcntl.flock(fhandle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            return True
        else:
            return False


@pytest.mark.parametrize("lock", [True, False])
def test_ConfigFile_lock(tmp_path, lock):
    install_dir = tmp_path / "install-dir"
    config_object = {
        'a': 10,
        'b': [1, 2, 3],
    }
    install_dir.mkdir(parents=True)
    config_path = install_dir / "bentobox-config.json"
    with open(config_path, "w") as fout:
       fout.write(json.dumps(config_object))

    with mock.patch("bentobox.box_file.get_install_dir", mock.MagicMock(return_value=install_dir)):
        config_file = _box_file.ConfigFile(lock=lock)
        locked = is_locked(config_file.path)
        assert not is_locked(config_file.path)
        with config_file:
            locked = is_locked(config_file.path)
            assert locked == lock
        locked = is_locked(config_file.path)
        assert not is_locked(config_file.path)
        
    
@pytest.mark.parametrize("lock", [True, False])
def test_ConfigFile_is_locked(tmp_path, lock):
    install_dir = tmp_path / "install-dir"
    install_dir.mkdir(parents=True)

    with mock.patch("bentobox.box_file.get_install_dir", mock.MagicMock(return_value=install_dir)):
        config_file = _box_file.ConfigFile(lock=lock)
        assert not config_file.is_locked()
        with config_file:
            assert config_file.is_locked() == lock
        assert not config_file.is_locked()


@pytest.mark.parametrize("lock", [True, False])
@pytest.mark.parametrize("obj", [{}, {'a': 10, 'b': [1, 2]}])
def test_ConfigFile_store_load(tmp_path, lock, obj):
    install_dir = tmp_path / "install-dir"
    install_dir.mkdir(parents=True)

    with mock.patch("bentobox.box_file.get_install_dir", mock.MagicMock(return_value=install_dir)):
        config_file = _box_file.ConfigFile(lock=lock)
        with config_file:
            config_file.store(obj)
            c_obj = config_file.load()
            assert c_obj == obj
            assert c_obj is not obj
        

@pytest.mark.parametrize("lock", [True, False])
@pytest.mark.parametrize("obj", [{}, {'a': 10, 'b': [1, 2]}])
def test_ConfigFile_config_getter_setter(tmp_path, lock, obj):
    install_dir = tmp_path / "install-dir"
    install_dir.mkdir(parents=True)

    new_obj = {'x': 100}
    with mock.patch("bentobox.box_file.get_install_dir", mock.MagicMock(return_value=install_dir)):
        config_file = _box_file.ConfigFile(lock=lock)
        with config_file:
            config_file.store(obj)
            c_obj = config_file.load()
            assert c_obj == obj
            assert c_obj is not obj
            c_obj2 = config_file.config
            assert c_obj2 == c_obj
            assert c_obj2 is not c_obj
            c_obj3 = config_file.config
            assert c_obj3 == c_obj2
            assert c_obj3 is c_obj2
            config_file.config = new_obj
            c_obj4 = config_file.config
            assert c_obj4 == new_obj
            assert c_obj4 is new_obj
            c_obj5 = config_file.config
            assert c_obj5 == c_obj4
            assert c_obj5 is c_obj4
        

def test_ConfigFile_load_empty(tmp_path):
    install_dir = tmp_path / "install-dir"
    install_dir.mkdir(parents=True)

    with mock.patch("bentobox.box_file.get_install_dir", mock.MagicMock(return_value=install_dir)):
        config_file = _box_file.ConfigFile()
        with config_file:
            assert config_file.load() is None


@pytest.mark.parametrize("exists", [False, True])
def test_get_config(tmp_path, exists):
    install_dir = tmp_path / "install-dir"
    config_path = install_dir / "bentobox-config.json"
    config_object = {
        'a': 10,
        'b': [1, 2, 3],
    }
    if exists:
        install_dir.mkdir(parents=True)
        with open(config_path, "w") as fout:
           fout.write(json.dumps(config_object))
    with mock.patch("bentobox.box_file.get_install_dir", mock.MagicMock(return_value=install_dir)):
        config = _box_file.get_config()
    if exists:
        assert config == config_object
    else:
        assert config is None
    

_WI_NONE = _box_file.WrapInfo(wrap_mode=_box_file.WrapMode.NONE, wraps=None)
_WI_ALL = _box_file.WrapInfo(wrap_mode=_box_file.WrapMode.ALL, wraps=None)
_WI_SINGLE = _box_file.WrapInfo(wrap_mode=_box_file.WrapMode.SINGLE, wraps="abc")
_WI_MULTIPLE = _box_file.WrapInfo(wrap_mode=_box_file.WrapMode.MULTIPLE, wraps=['x1', 'x2'])

@pytest.mark.parametrize("state_wrap_info, wrapping, wrap_info", [
    [_WI_SINGLE, True, _WI_SINGLE],
    [_WI_MULTIPLE, False, _WI_NONE],
])
def test_get_wrap_info(state_wrap_info, wrapping, wrap_info):
    print(state_wrap_info)
    print(wrap_info)
    state = {
        'wrap_mode': state_wrap_info.wrap_mode,
        'wraps': state_wrap_info.wraps,
    }
    with mock.patch("bentobox.box_file.WRAPPING", wrapping):
        assert _box_file.get_wrap_info(state) == wrap_info


@pytest.mark.parametrize("in_environ, venv_bin_dir, out_environ", [
    [{}, '/tmp/bin', {'PATH': '/tmp/bin'}],
    [{'MY_VAR': 'alpha'}, '/tmp/bin', {'MY_VAR': 'alpha', 'PATH': '/tmp/bin'}],
    [{'PATH': ':'}, '/tmp/bin', {'PATH': '/tmp/bin'}],
    [{'PATH': '::::'}, '/tmp/bin', {'PATH': '/tmp/bin'}],
    [{'PATH': '::/opt/bin::'}, '/tmp/bin', {'PATH': '/tmp/bin:/opt/bin'}],
    [{'PATH': '/bin:/opt/bin:/usr/bin'}, '/tmp/bin', {'PATH': '/tmp/bin:/bin:/opt/bin:/usr/bin'}],
    [{'MY_VAR': '10', 'PATH': '/bin:'}, '/tmp/bin', {'MY_VAR': '10', 'PATH': '/tmp/bin:/bin'}],
])
def test_get_environ(in_environ, venv_bin_dir, out_environ):
    config = {
        'venv_bin_dir': venv_bin_dir,
    }
    with mock.patch('os.environ', in_environ):
        assert _box_file.get_environ(config) == out_environ


_ELIST = [('a.x', 'f', 0o755), ('b.x', 'f', 0o755),
          ('c.x', 'f', 0o644), ('d.x', 'd', 0o755)]

def _mk_entries(bindir, elist):
    for basename, etype, emod in elist:
        epath = bindir / basename
        if etype == 'f':
            epath.touch()
        else:
            epath.mkdir()
        epath.chmod(emod)


@pytest.mark.parametrize("elist, bindir, config, exe_files", [
    [_ELIST, None, None, None],
    [[],     None, None, None],
    [[],     None, {},   []],
    [_ELIST, None, {},   ['a.x', 'b.x']],
    [[],     "xy", None, []],
    [_ELIST, "xy", {},   ['a.x', 'b.x']],
])
def test_find_executables(tmp_path, elist, bindir, config, exe_files):
    venv_bin_dir = tmp_path / 'venv' / 'bin'
    venv_bin_dir.mkdir(parents=True)
    if config is not None:
        config['venv_bin_dir'] = venv_bin_dir
    if bindir:
        bindir = tmp_path / bindir
        bindir.mkdir(parents=True)
        kwargs = {'bindir': bindir}
        use_bindir = bindir
    else:
        kwargs = {}
        use_bindir = venv_bin_dir
    _mk_entries(use_bindir, elist)
    with mock.patch("bentobox.box_file.get_config", mock.MagicMock(return_value=config)):
        exe_list = _box_file.find_executables(**kwargs)
    assert exe_list == exe_files
    

@pytest.mark.parametrize("elist, command, is_installed", [
    [[],     'a.x', False],
    [_ELIST, 'a.x', True],
    [_ELIST, 'c.x', False],
    [_ELIST, 'd.x', False],
])
def test_check_installed_command(tmp_path, elist, command, is_installed):
    venv_bin_dir = tmp_path / 'venv' / 'bin'
    venv_bin_dir.mkdir(parents=True)
    _mk_entries(venv_bin_dir, elist)
    config = {'venv_bin_dir': venv_bin_dir}
    with mock.patch("bentobox.box_file.get_config", mock.MagicMock(return_value=config)):
        if is_installed:
            _box_file.check_installed_command(command)
        else:
            with pytest.raises(_box_file.BoxError) as exc_info:
                _box_file.check_installed_command(command)
            assert str(exc_info.value) == str(_box_file.BoxError("command {} not installed".format(command)))


_WI_NONE = _box_file.WrapInfo(wrap_mode=_box_file.WrapMode.NONE, wraps=None)
_WI_ALL = _box_file.WrapInfo(wrap_mode=_box_file.WrapMode.ALL, wraps=None)
_WI_SINGLE = _box_file.WrapInfo(wrap_mode=_box_file.WrapMode.SINGLE, wraps="abc")
_WI_MULTIPLE = _box_file.WrapInfo(wrap_mode=_box_file.WrapMode.MULTIPLE, wraps=['x1', 'x2'])
@pytest.mark.parametrize("elist, wrap_info, failing", [
    [[], _box_file.WrapInfo(wrap_mode=_box_file.WrapMode.NONE, wraps=None), None],
    [[], _box_file.WrapInfo(wrap_mode=_box_file.WrapMode.ALL, wraps=None), None],
    [_ELIST, _box_file.WrapInfo(wrap_mode=_box_file.WrapMode.SINGLE, wraps='a.x'), None],
    [_ELIST, _box_file.WrapInfo(wrap_mode=_box_file.WrapMode.SINGLE, wraps='c.x'), 'c.x'],
    [_ELIST, _box_file.WrapInfo(wrap_mode=_box_file.WrapMode.SINGLE, wraps='d.x'), 'd.x'],
    [_ELIST, _box_file.WrapInfo(wrap_mode=_box_file.WrapMode.SINGLE, wraps='e.x'), 'e.x'],
    [_ELIST, _box_file.WrapInfo(wrap_mode=_box_file.WrapMode.MULTIPLE, wraps={'ax': 'a.x', 'bx': 'b.x'}), None],
    [_ELIST, _box_file.WrapInfo(wrap_mode=_box_file.WrapMode.MULTIPLE, wraps={'ax': 'a.x', 'bx': 'c.x'}), 'c.x'],
    [_ELIST, _box_file.WrapInfo(wrap_mode=_box_file.WrapMode.MULTIPLE, wraps={'dx': 'd.x', 'cx': 'c.x'}), 'd.x'],
])
def test_check_wrap_info(elist, tmp_path, wrap_info, failing):
    venv_bin_dir = tmp_path / 'venv' / 'bin'
    venv_bin_dir.mkdir(parents=True)
    _mk_entries(venv_bin_dir, elist)
    config = {'venv_bin_dir': venv_bin_dir}
    with mock.patch("bentobox.box_file.get_config", mock.MagicMock(return_value=config)):
        if failing:
            with pytest.raises(_box_file.BoxError) as exc_info:
                _box_file.check_wrap_info(wrap_info)
            assert str(exc_info.value) == "command {} not installed".format(failing)
        else:
            _box_file.check_wrap_info(wrap_info)


@pytest.mark.parametrize("in_config, out_config", [
    [{}, None],
    [{'i': 1, 'f': 1.1, 's': 'one', 'b': True, 'n': None, 'l': [2, 2.2, 'two', False]}, None],
    [{'e': _box_file.WrapMode.SINGLE}, {'e': 'SINGLE'}],
    [{'e': [_box_file.WrapMode.SINGLE]}, {'e': ['SINGLE']}],
    [{'e': {'e1': [_box_file.WrapMode.SINGLE]}}, {'e': {'e1': ['SINGLE']}}],
    [{'x': all}, TypeError(all)],
    [{'i': 10, 'l': [1, all]}, TypeError(all)],
])
def test_tojson(in_config, out_config):
    if isinstance(out_config, Exception):
        with pytest.raises(type(out_config)) as exc_info:
            _box_file.tojson(in_config)
        assert str(exc_info.value) == str(out_config)
    else:
        if out_config is None:
            out_config = in_config
        assert _box_file.tojson(in_config) == out_config


@pytest.mark.parametrize("repo", [None, 10, 'abc', {'a': 1}])
def test_get_repo(repo):
    with mock.patch("bentobox.box_file.STATE", {'repo': repo}):
        assert _box_file.get_repo() is repo


@pytest.mark.parametrize("wrap_info, box_type", [
    [_box_file.WrapInfo(wrap_mode=_box_file.WrapMode.NONE, wraps=None),
     'installer'],
    [_box_file.WrapInfo(wrap_mode=_box_file.WrapMode.ALL, wraps=None),
     'wraps(*)'],
    [_box_file.WrapInfo(wrap_mode=_box_file.WrapMode.SINGLE, wraps="abc"),
     'wraps(abc)'],
    [_box_file.WrapInfo(wrap_mode=_box_file.WrapMode.MULTIPLE, wraps=['abc']),
     'wraps[abc]'],
    [_box_file.WrapInfo(wrap_mode=_box_file.WrapMode.MULTIPLE, wraps=['x1', 'x2']),
     'wraps[x1, x2]'],
])
def test_get_box_type(wrap_info, box_type):
    state = {
        'wrap_mode': wrap_info.wrap_mode,
        'wraps': wrap_info.wraps,
    }
    assert _box_file.get_box_type(state) == box_type


class Check:
    def __call__(self, value):
        raise NotImplementedError()


class CheckValue(Check):
    def __init__(self, value):
        self.value = value

    def __call__(self, value):
        return value == self.value

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.value)


class CheckIsInstance(Check):
    def __init__(self, type_list):
        self.type_list = type_list

    def __call__(self, value):
        return isinstance(value, self.type_list)

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.type_list)


_FILE_TTY = mock.MagicMock()
_FILE_TTY.isatty = mock.MagicMock(return_value=True)
_FILE_NOTTY = mock.MagicMock()
_FILE_NOTTY.isatty = mock.MagicMock(return_value=False)

_NCOLUMNS = 37
@pytest.mark.parametrize("sys_stderr, kwargs, checks", [
    [_FILE_TTY, {},
     {'_header': _box_file.HEADER, '_verbose_level': _box_file.get_verbose_level(), '_prev_line': None}],
    [_FILE_TTY, {'header': 'bbox> ', 'verbose_level': 0},
     {'_header': "bbox> ", '_verbose_level': 0, '_persistent': True,
      '_columns': None, '_file': CheckIsInstance(io.StringIO)}],
    [_FILE_TTY, {'verbose_level': 1},
     {'_verbose_level': 1, '_persistent': False,
      '_columns': _NCOLUMNS, '_file': _FILE_TTY}],
    [_FILE_NOTTY, {'verbose_level': 1},
     {'_verbose_level': 1, '_persistent': True,
      '_columns': None, '_file': _FILE_NOTTY}],
    [_FILE_TTY, {'verbose_level': 2},
     {'_verbose_level': 2, '_persistent': True,
      '_columns': None, '_file': _FILE_TTY}],
    [_FILE_NOTTY, {'verbose_level': 2},
     {'_verbose_level': 2, '_persistent': True,
      '_columns': None, '_file': _FILE_NOTTY}],
])
def test_Output_init(sys_stderr, kwargs, checks):
    with mock.patch("os.get_terminal_size", mock.MagicMock(return_value=(_NCOLUMNS, 123))), \
         mock.patch("sys.stderr", sys_stderr):
        output = _box_file.Output(**kwargs)
    for attr, check in checks.items():
        if not isinstance(check, Check):
            check = CheckValue(check)
        assert check(getattr(output, attr))


@pytest.mark.parametrize("persistent, columns, header, in_strings, output_string", [
    [False,   80, "bbox> ", [], ''],
    [True,    80, "bbox> ", [], ''],
    [False,   80, "bbox> ", ["hello"], 'bbox> hello\r           \r'],
    [True,    80, "bbox> ", ["hello"], 'bbox> hello\n'],
    [False,   80, "",       ["hello", "world!", "bye", "world"], 'hello\r     \rworld!\r      \rbye\r   \rworld\r     \r'],
    [True,    80, "",       ["hello", "world!", "bye", "world"], 'hello\nworld!\nbye\nworld\n'],
    [False,    3, "bbox> ", ["hello", "world!"], 'bbo\r   \rbbo\r   \r'],
    [True,     3, "bbox> ", ["hello", "world!"], 'bbox> hello\nbbox> world!\n'],
    [False,   10, "bbox> ", ["hello", "world!"], 'bbox> hell\r          \rbbox> worl\r          \r'],
    [True,    10, "bbox> ", ["hello", "world!"], 'bbox> hello\nbbox> world!\n'],
    [False, None, "bbox> ", ["hello", "world!"], 'bbox> hello\r           \rbbox> world!\r            \r'],
    [True,  None, "bbox> ", ["hello", "world!"], 'bbox> hello\nbbox> world!\n'],
])
def test_Output_call(persistent, columns, header, in_strings, output_string):
    if persistent:
        verbose_level = 2
    else:
        verbose_level = 0
    stderr = io.StringIO()
    with _box_file.Output(verbose_level=verbose_level, header=header) as output:
        output._file = stderr
        output._columns = columns
        output._persistent = persistent
        for in_string in in_strings:
            output(in_string)
    assert stderr.getvalue() == output_string


@pytest.mark.parametrize("persistent, verbose_level, returncode, raising, output_string", [
    [False, 0, 0, False, ""],
    [False, 2, 7, False, ""],
    [False, 2, 7, True,  ""],
    [False, 3, 7, False, ""],
    [False, 3, 7, True,  ""],
    [True,  2, 0, False, "bb: $ ./myprog -x 'a b'\n"],
    [True,  2, 0, True,  "bb: $ ./myprog -x 'a b'\n"],
    [True,  3, 7, False, "bb: $ ./myprog -x 'a b'\nbb: value == <a b>\nbb: \n"],
    [True,  3, 7, True,  "bb: $ ./myprog -x 'a b'\nbb: value == <a b>\nbb: \n"],
    [True,  0, 7, False, "bb: $ ./myprog -x 'a b'\nbb: value == <a b>\nbb: \n"],
    [True,  0, 7, True,  "bb: $ ./myprog -x 'a b'\nbb: value == <a b>\nbb: \n"],
])
def test_Output_run_command(persistent, verbose_level, returncode, raising, output_string):
    args = ['./myprog', '-x', 'a b']
    out = subprocess.CompletedProcess(
        args=args,
        returncode=returncode,
        stdout=b"value == <a b>\n",
    )
    run_mock = mock.MagicMock(return_value=out)
    stderr = io.StringIO()
    with _box_file.Output(verbose_level=verbose_level, header="bb: ") as output:
        output._file = stderr
        output._columns = 1000
        output._verbose_level = verbose_level
        output._persistent = persistent
        with mock.patch("subprocess.run", run_mock):
            if returncode and raising:
                with pytest.raises(_box_file.BoxError) as exc_info:
                    output.run_command(args, raising=raising)
                assert str(exc_info.value) == "command ./myprog -x 'a b' failed [{}]".format(returncode)
            else:
                output.run_command(args, raising=raising)
    print(repr(stderr.getvalue()))
    print(repr(output_string))
    assert stderr.getvalue() == output_string


def test_set_install_dir(tmp_path):
    install_dir = tmp_path / "install"
    orig_install_dir = _box_file.get_install_dir()
    assert str(orig_install_dir) != str(install_dir)
    with _box_file.set_install_dir(install_dir):
        assert _box_file.get_install_dir() == install_dir
    assert str(_box_file.get_install_dir()) == str(orig_install_dir)


@pytest.mark.parametrize("pre_mode, post_exists", [
    [0o444, True],
    [0o744, True],
    [0o111, True],
    [0o444, False],
])
def test_set_write_mode_exists(tmp_path, pre_mode, post_exists):
    tmp_file = tmp_path / 'file'
    tmp_file.touch()
    tmp_file.chmod(pre_mode)
    init_mode = tmp_file.stat().st_mode
    with _box_file.set_write_mode(tmp_file):
        with open(tmp_file, 'w') as fout:
            fout.write("...\n")
        if not post_exists:
            tmp_file.unlink()
    if post_exists:
        assert tmp_file.stat().st_mode == init_mode


def test_set_write_mode_missing(tmp_path):
    tmp_file = tmp_path / 'file'
    assert not tmp_file.exists()
    with _box_file.set_write_mode(tmp_file):
        assert not tmp_file.exists()
    assert not tmp_file.exists()
    

@pytest.mark.parametrize("output, length", [
    ["", 0],
    [_box_file.MARK_END_OF_HEADER, 0],
    [_box_file.MARK_END_OF_HEADER + '\n', 0],
    ['x' + _box_file.MARK_END_OF_HEADER + '\n', 1 + len(_box_file.MARK_END_OF_HEADER) + 1],
    ['\n' + _box_file.MARK_END_OF_HEADER + '\n', 1],
    ['x\n' + _box_file.MARK_END_OF_HEADER + '\n', 2],
    ['x\n\nyy\n' + _box_file.MARK_END_OF_HEADER + '\n', 6],
])
def test_get_header_len(tmp_path, output, length):
    tmp_file = tmp_path / 'file'
    with open(tmp_file, 'w') as fout:
        fout.write(output)
    assert _box_file.get_header_len(tmp_file) == length


@pytest.mark.parametrize("fill_len, kwargs, output", [
    [0, {}, ''],
    [1, {}, '\n'],
    [10, {}, '#########\n'],
    [100, {}, '################################################################################\n##################\n'],
    [10, {'line_len': 5}, '#####\n###\n'],
])
def test_filler(fill_len, kwargs, output):
    assert _box_file.filler(fill_len, **kwargs) == output
    assert len(output) == fill_len


def _mk_state(state):
    base_state = {
        'box_name': 'test-box-name',
        'box_version': 'abc123',
        'python_interpreter': '/opt/python36/bin/python',
        'install_dir': None,
        'update_shebang': True,
        'wrap_mode': _box_file.WrapMode.NONE,
        'wraps': None,
        'verbose_level': 2,
        'freeze_env': True,
    }
    base_state.update(state)
    return base_state


@pytest.mark.parametrize("init_state", [
    {},
    {'x': 10},
    {'values': [1, 2, 3], 'alpha': 'xyz'},
    {'big_big_var': ":xy:" * 1024},
])
@pytest.mark.parametrize("in_place", [True, False])
def test_replace_state(tmp_path, in_place, init_state):
    state = _mk_state({})
    state.update(init_state)
    tmp_box_file = tmp_path / "box-file"
    source_file = tmp_path / Path(_box_file.__file__).name
    shutil.copy(_box_file.__file__, source_file)
    if not in_place:
        shutil.copy(_box_file.__file__, tmp_box_file)
    with mock.patch("bentobox.box_file.FILE_PATH", str(source_file)):
        _box_file.replace_state(tmp_box_file, state)
    box_module = load_py_module(tmp_box_file)
    assert _box_file.tojson(box_module.STATE) == _box_file.tojson(state)


@pytest.mark.parametrize("old_state, install_dir, python_interpreter, new_state", [
    [
        {'update_shebang': True, 'python_interpreter': 'py',
         '__internal__': {'python_interpreter': 'orig_py', 'install_dir': None},
        },
        None,
        None,
        {'update_shebang': True, 'python_interpreter': 'py',
         '__internal__': {'python_interpreter': 'orig_py', 'install_dir': None},
        },
    ],
    [
        {'update_shebang': True, 'python_interpreter': 'py',
         '__internal__': {'python_interpreter': 'orig_py', 'install_dir': None},
        },
        None,
        'py',
        {'update_shebang': True, 'python_interpreter': 'py',
         '__internal__': {'python_interpreter': 'orig_py', 'install_dir': None},
        },
    ],
    [
        {'update_shebang': False, 'python_interpreter': 'py',
         '__internal__': {'python_interpreter': 'orig_py', 'install_dir': None},
        },
        None,
        'new_py',
        {'update_shebang': False, 'python_interpreter': 'py',
         '__internal__': {'python_interpreter': 'orig_py', 'install_dir': None},
        },
    ],
    [
        {'update_shebang': True, 'python_interpreter': 'py',
         '__internal__': {'python_interpreter': None, 'install_dir': None},
        },
        None,
        'new_py',
        {'update_shebang': True, 'python_interpreter': 'new_py',
         '__internal__': {'python_interpreter': 'py', 'install_dir': None},
        },
    ],
    [
        {'update_shebang': True, 'python_interpreter': 'py', 'install_dir': '/xx',
         '__internal__': {'python_interpreter': None, 'install_dir': None},
        },
        '/yy',
        'new_py',
        {'update_shebang': True, 'python_interpreter': 'new_py', 'install_dir': '/yy',
         '__internal__': {'python_interpreter': 'py', 'install_dir': '/xx'},
        },
    ],
    [
        {'update_shebang': True, 'python_interpreter': 'py', 'install_dir': '/xx',
         '__internal__': {'python_interpreter': 'orig_py', 'install_dir': '/uuu'},
        },
        '/yy',
        'new_py',
        {'update_shebang': True, 'python_interpreter': 'new_py', 'install_dir': '/yy',
         '__internal__': {'python_interpreter': 'orig_py', 'install_dir': '/uuu'},
        },
    ],
])
def test_update_box_header(tmp_path, old_state, install_dir, python_interpreter, new_state):
    old_state = _mk_state(old_state)
    new_state = _mk_state(new_state)

    tmp_box_file = tmp_path / "box-file"
    shutil.copy(_box_file.__file__, tmp_box_file)
    with mock.patch("bentobox.box_file.FILE_PATH", str(tmp_box_file)), \
         mock.patch("bentobox.box_file.UPDATE_SHEBANG", old_state['update_shebang']), \
         mock.patch("bentobox.box_file.STATE", old_state):
        _box_file._update_box_header(mock.MagicMock(), install_dir=install_dir, python_interpreter=python_interpreter)
    box_module = load_py_module(tmp_box_file)
    assert _box_file.tojson(box_module.STATE) == _box_file.tojson(new_state)


@pytest.mark.parametrize("old_state, new_state", [
    [
        {'install_dir': '/new_dir', 'python_interpreter': 'new_py',
         '__internal__': {'python_interpreter': 'old_py', 'install_dir': '/old_dir'},
        },
        {'install_dir': '/old_dir', 'python_interpreter': 'old_py',
         '__internal__': {'python_interpreter': None, 'install_dir': None},
        },
    ],
])
def test_reset_box_header(tmp_path, old_state, new_state):
    old_state = _mk_state(old_state)
    new_state = _mk_state(new_state)

    tmp_box_file = tmp_path / "box-file"
    shutil.copy(_box_file.__file__, tmp_box_file)
    with mock.patch("bentobox.box_file.FILE_PATH", str(tmp_box_file)), \
         mock.patch("bentobox.box_file.STATE", old_state):
        _box_file._reset_box_header(mock.MagicMock())
    box_module = load_py_module(tmp_box_file)


@pytest.mark.parametrize("kwargs, checks", [
    [{},
     {}],
    [{'install_dir': '/tmp/x'},
     {'install_dir': '/tmp/x'}],
    [{'install_dir': '/tmp/x', 'wrap_info': _box_file.WrapInfo(_box_file.WrapMode.MULTIPLE, {'a': 'a.x', 'b': 'b.x'})},
     {'install_dir': '/tmp/x', 'wrap_mode': _box_file.WrapMode.MULTIPLE, 'wraps': {'a': 'a.x', 'b': 'b.x'}}],
    [{'install_dir': None, 'verbose_level': 7, 'freeze_env': False, 'update_shebang': False},
     {'install_dir': None, 'verbose_level': 7, 'freeze_env': False, 'update_shebang': False}],
])
def test_configure(tmp_path, kwargs, checks):
    old_state = _mk_state({})
    tmp_box_file = tmp_path / "box-file"
    shutil.copy(_box_file.__file__, tmp_box_file)
    rs_mock = mock.MagicMock()
    with mock.patch("bentobox.box_file.FILE_PATH", str(tmp_box_file)), \
         mock.patch("bentobox.box_file.STATE", old_state), \
         mock.patch("bentobox.box_file.replace_state", rs_mock):
        _box_file.configure(tmp_box_file, **kwargs)
    c_args, c_kwargs = rs_mock.call_args
    assert not c_kwargs
    tojson = _box_file.tojson
    assert tojson(c_args[0]) == tojson(tmp_box_file)
    new_state = c_args[1]
    for key, value in checks.items():
        assert tojson(new_state[key]) == tojson(value)
