import io
import json
import fcntl
import os
import subprocess
import sys

from pathlib import Path
from unittest import mock

import pytest


from bentobox import box_file as _box_file


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

@pytest.mark.parametrize("box_name", [
    None,
    "alpha-omega",
])
def test_default_install_dir(box_name):
    actual_box_name = box_name
    if actual_box_name is None:
        actual_box_name = _box_file.STATE['box_name']
    value = _box_file.default_install_dir(box_name)
    assert value == _box_file.DEFAULT_INSTALL_ROOT_DIR / actual_box_name


@pytest.mark.parametrize("box_name, var_install_dir, state_install_dir, install_dir", [
    ["abc", None, None, None],
    ["abc", Path('/a'), None, Path('/a')],
    ["abc", None, '/b', Path('/b')],
    ["abc", Path('/a'), '/b', Path('/a')],
])
def test_get_install_dir(box_name, var_install_dir, state_install_dir, install_dir):
    state = _box_file.STATE.copy()
    state['install_dir'] = state_install_dir
    state['box_name'] = box_name
    if install_dir is None:
        install_dir = _box_file.default_install_dir(box_name).expanduser()
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
