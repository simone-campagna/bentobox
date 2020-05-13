import json
import fcntl
import os

from pathlib import Path
from unittest import mock

import pytest


from bentobox import box_file as _box_file


def test_FILE_PATH():
    assert _box_file.FILE_PATH is None


def test_DEFAULT_INSTALL_ROOT_DIR():
    assert _box_file.DEFAULT_INSTALL_ROOT_DIR == Path("~") / ".bentobox" / "boxes"


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
    
