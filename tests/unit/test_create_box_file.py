# import contextlib
import os
import pytest
from unittest import mock

from pathlib import Path

from bentobox.create_box_file import (
    check_box_name,
    create_box_file,
    check_box,
    DownloadMode,
)
from bentobox.env import (
    DEFAULT_PYTHON_INTERPRETER,
    INIT_VENV_PACKAGES,
)
from bentobox.errors import (
    BoxNameError,
    BoxPathError,
)
from bentobox.util import load_py_module
from bentobox import box_file as _box_file


@pytest.mark.parametrize("box_name", [
    "box",
    "_box",
    "box01",
    "box-01",
    "my-box",
])
def test_check_box_name(box_name):
    assert check_box_name(box_name) == box_name


@pytest.mark.parametrize("box_name", [
    "0box",
    "-box",
    ".box",
    "my.box",
])
def test_check_box_name_error(box_name):
    with pytest.raises(BoxNameError) as exc_info:
        check_box_name(box_name)
    assert str(exc_info.value) == box_name


@pytest.mark.parametrize("install_dir", [None, "install/mybox-dir"])
def test_check_box(tmp_path, install_dir):
    box_path = tmp_path / "mybox"
    box_mock = mock.MagicMock()
    load_py_mock = mock.MagicMock(return_value=box_mock)
    with mock.patch("bentobox.create_box_file.load_py_module", load_py_mock):
        check_box(box_path, install_dir)
    assert load_py_mock.call_args == ((box_path,),)
    assert box_mock.check.call_args == ((install_dir,),)


@pytest.mark.parametrize("create_kwargs, params, expected", [
    [
        {
            'box_name': 'box-example',
            'force_overwrite': False,
            'check': False,
        },
        {
            'box_file_exists': False,
            'add_requirements_output': [[], []],
            'get_requirements_output': [[], []],
            'get_package_paths_output': [[]],
        },
        {
            'package_names': [],
            'state': {
                'update_shebang': True,
                'freeze_env': True,
                'use_pypi': False,
                'init_venv_packages': [],
                'packages': [],
                'pip_install_args': [],
                'wrap_mode': _box_file.WrapMode.NONE,
                'wraps': None,
            },
        },
    ],
    [
        {
            'box_name': 'box-example',
            'check': False,
            'wrap_info': _box_file.WrapInfo(_box_file.WrapMode.SINGLE, 'prog.x'),
        },
        {
            'box_file_exists': True,
            'add_requirements_output': [[], []],
            'get_requirements_output': [[], []],
            'get_package_paths_output': [[]],
        },
        {
            'package_names': [],
            'state': {
                'update_shebang': True,
                'freeze_env': True,
                'use_pypi': False,
                'init_venv_packages': [],
                'packages': [],
                'pip_install_args': [],
                'wrap_mode': _box_file.WrapMode.SINGLE,
                'wraps': 'prog.x',
            },
        },
    ],
    [
        {
            'box_name': 'box-example',
            'force_overwrite': True,
            'check': False,
        },
        {
            'box_file_exists': True,
            'add_requirements_output': [[], []],
            'get_requirements_output': [[], []],
            'get_package_paths_output': [[]],
        },
        {
            'package_names': [],
            'state': {
                'update_shebang': True,
                'freeze_env': True,
                'use_pypi': False,
                'init_venv_packages': [],
                'packages': [],
                'pip_install_args': [],
            },
        },
    ],
    [
        {
            'box_name': 'box-example',
            'output_path': "missing-dir/box_example.x",
            'force_overwrite': True,
            'verbose_level': 1,
            'init_venv_packages': (),
            'pip_install_args': ['-arg0', '--arg1'],
            'check': True,
            'packages': (),
        },
        {
            'box_file_exists': False,
            'add_requirements_output': [[], []],
            'get_requirements_output': [[], []],
            'get_package_paths_output': [[]],
        },
        {
            'package_names': [],
            'state': {
                'update_shebang': True,
                'freeze_env': True,
                'use_pypi': False,
                'init_venv_packages': [],
                'packages': [],
                'pip_install_args': ['-arg0', '--arg1'],
            },
        },
    ],
    [
        {
            'box_name': 'box-example',
            'output_path': "box_example.x",
            'force_overwrite': True,
            'verbose_level': 1,
            'freeze_env': False,
            'freeze_pypi': False,
            'check': True,
            'init_venv_packages': ['xp0', 'xp1>1'],
            'packages': ['/tmp/yp0.egg']
        },
        {
            'box_file_exists': True,
            'add_requirements_output': [["xp0", "xp1"], ['xp1==4.4.4', 'yp0']],
            'get_requirements_output': [["xp0==9.8.7", "xp1==4.4.4"], ['xp1==4.4.4', 'yp0===1.3.5']],
            'get_package_paths_output': [[('yp0', 'yp0-1.3.5.tgz')]],
        },
        {
            'package_names': ["yp0"],
            'state': {
                'update_shebang': True,
                'freeze_env': False,
                'use_pypi': True,
                'init_venv_packages': ["xp0==9.8.7", "xp1==4.4.4"],
                'packages': ["xp1==4.4.4", "yp0===1.3.5"],
                'pip_install_args': [],
            },
        },
    ],
    [
        {
            'box_name': 'box-example',
            'output_path': "box_example.x",
            'force_overwrite': True,
            'verbose_level': 1,
            'freeze_env': False,
            'freeze_pypi': False,
            'check': True,
            'init_venv_packages': ['xp0', 'xp1>1'],
            'packages': ['/tmp/yp0.egg']
        },
        {
            'box_file_exists': True,
            'add_requirements_output': [["xp0", "xp1"], ['xp1==4.4.4', 'yp0']],
            'get_requirements_output': [["xp0===9.8.7", "xp1===4.4.4"], ['xp1===4.4.4', 'yp0===1.3.5']],
            'get_package_paths_output': [[('xp0', 'xp0-9.8.7.whl'), ('xp1', 'xp1-4.4.4.egg'), ('yp0', 'yp0-1.3.5.tgz')]],
        },
        {
            'package_names': ["xp0", "xp1", "yp0"],
            'state': {
                'update_shebang': True,
                'freeze_env': False,
                'use_pypi': True,
                'init_venv_packages': ["xp0===9.8.7", "xp1===4.4.4"],
                'packages': ["xp1===4.4.4", "yp0===1.3.5"],
                'pip_install_args': [],
            },
        },
    ],
])
def test_create_box_file(tmp_path, create_kwargs, params, expected, monkeypatch):
    workdir = tmp_path / 'workdir'
    workdir.mkdir()

    monkeypatch.chdir(workdir)

    box_file = create_kwargs.get('output_path', None)
    box_name = create_kwargs['box_name']
    if box_file is None:
        box_file = workdir / box_name
    else:
        box_file = Path(box_file)
    box_file = box_file.resolve()

    freeze_pypi = create_kwargs.get('freeze_pypi', True)
    check = create_kwargs.get('check', True)
    init_venv_packages = create_kwargs.get('init_venv_packages', INIT_VENV_PACKAGES)
    verbose_level = create_kwargs.get('verbose_level', _box_file.VERBOSE_LEVEL)
    force_overwrite = create_kwargs.get('force_overwrite', False)
    box_file_exists = params.get('box_file_exists', False)
    if box_file_exists:
        box_file.touch()

    exc = None
    print(box_file_exists, force_overwrite)
    if box_file_exists and not force_overwrite:
        exc = BoxPathError("file {!r} already exists".format(str(box_file)))

    add_requirements_input = [create_kwargs.get('init_venv_packages', INIT_VENV_PACKAGES),
                              create_kwargs.get('packages', ())]
    add_requirements_output = params['add_requirements_output']
    get_requirements_output = params['get_requirements_output']
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    get_package_paths_output = []
    for plist in params['get_package_paths_output']:
        olist = []
        for pname, ppath in plist:
            ppath = data_dir / ppath
            with open(ppath, "w") as fout:
                fout.write("...")
            olist.append((pname, ppath))
        get_package_paths_output.append(olist)

    add_requirements_mock = mock.MagicMock(side_effect=add_requirements_output)
    get_requirements_mock = mock.MagicMock(side_effect=get_requirements_output)
    get_package_paths_mock = mock.MagicMock(side_effect=get_package_paths_output)
    check_box_name_mock = mock.MagicMock(side_effect=lambda bn: bn)
    check_box_mock = mock.MagicMock()
    with mock.patch("bentobox.create_box_file.check_box_name", check_box_name_mock), \
         mock.patch("bentobox.create_box_file.check_box", check_box_mock), \
         mock.patch("bentobox.create_box_file.PackageRepo.add_requirements", add_requirements_mock), \
         mock.patch("bentobox.create_box_file.PackageRepo.get_requirements", get_requirements_mock), \
         mock.patch("bentobox.create_box_file.PackageRepo.get_package_paths", get_package_paths_mock):
            if exc is not None:
                with pytest.raises(type(exc)) as exc_info:
                    create_box_file(**create_kwargs)
                assert str(exc_info.value) == str(exc)
                return
            else:
                box_file_path = create_box_file(**create_kwargs)

    assert check_box_name_mock.call_args == ((box_name,),)
    assert get_package_paths_mock.call_args == ((), {'download_mode': DownloadMode.FREE, 'freeze_pypi': freeze_pypi})
    for add_requirements_input, add_requirements_call_arg in add_requirements_mock.call_arg_list:
        assert add_requirements_call_arg == (add_requirements_input,)

    print(box_file)
    assert box_file == box_file_path
    assert box_file.is_file()
    assert os.access(box_file, os.X_OK)
    package_names = []
    package_filenames = []
    package_hashes = []
    status = 'start'
    with open(box_file, 'r') as fbox:
        for lineno, line in enumerate(fbox):
            line = line.rstrip('\n')
            # print("{:<20} {}".format(status, line))
            if lineno == 0:
                shebang = line[2:]
                assert shebang == DEFAULT_PYTHON_INTERPRETER
            if status == 'start':
                if line == _box_file.MARK_REPO:
                    status = 'repo-start'
            elif status == 'repo-start':
                assert line.startswith('#')
                line = line[1:]
                assert not line
                status = 'repo-name'
            elif status == 'repo-name':
                assert line.startswith('#')
                package_names.append(line[1:])
                # print("+++", package_names)
                status = 'repo-filename'
            elif status == 'repo-filename':
                assert line.startswith('#')
                package_filenames.append(line[1:])
                status = 'repo-hash'
            elif status == 'repo-hash':
                assert line.startswith('#')
                package_hashes.append(line[1:])
                status = 'repo-data'
            elif status == 'repo-data':
                assert line.startswith('#')
                if not line[1:]:
                    status = 'repo-name'
            else:
                print("-----", line)

    if check:
        assert check_box_mock.call_count == 1
        args, kwargs = check_box_mock.call_args
        assert args[0] == box_file_path
    else:
        assert check_box_mock.call_count == 0

    assert package_names == expected['package_names']
    box_module = load_py_module(box_file_path)
    assert box_module.VERBOSE_LEVEL == verbose_level
    for key, value in expected.get('state', {}).items():
        if key == 'wrap_mode':
            assert box_module.STATE[key].name == value.name
        else:
            assert box_module.STATE[key] == value
