import collections
import shutil
import subprocess
import sys

from pathlib import Path
from unittest import mock

import pytest

from bentobox.errors import BoxPathError
from bentobox.package_info import PackageInfo, VersionSpec
from bentobox.package_repo import PackageRepo


def test_PackageRepo(tmp_path):
    prepo = PackageRepo(tmp_path)


def test_PackageRepo_create_package_from_file_err_missing(tmp_path):
    dist_file = tmp_path / "alpha-1.2.3.tar.gz"
    prepo = PackageRepo(tmp_path)
    with pytest.raises(BoxPathError) as exc_info:
        prepo.create_package(dist_file)
    assert str(exc_info.value) == str(BoxPathError("path {} does not exist".format(dist_file)))
    

def test_PackageRepo_create_package_from_file(tmp_path):
    dist_file = tmp_path / "alpha-1.2.3.tar.gz"
    dist_file.touch()
    prepo = PackageRepo(tmp_path)
    assert prepo.create_package(dist_file) == dist_file


def test_PackageRepo_create_package_from_dir_err_missing(tmp_path):
    src_dir = tmp_path / "alpha"
    src_dir.mkdir()
    setup_py_path = src_dir / "setup.py"
    prepo = PackageRepo(tmp_path)
    with pytest.raises(BoxPathError) as exc_info:
        prepo.create_package(src_dir)
    assert str(exc_info.value) == str(BoxPathError("path {} does not exist".format(setup_py_path)))


def test_PackageRepo_create_package_from_dir(tmp_path, examples_dir):
    src_dir = tmp_path / "calclib"
    shutil.copytree(examples_dir / "calclib", src_dir)
    setup_py_path = src_dir / "setup.py"
    assert setup_py_path.exists()
    dist_dir = src_dir / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    prepo = PackageRepo(tmp_path)
    dist_filename = "calclibxx-9.8.7.tgz"
    def create_dist_file(cmdline, *args, **kwargs):
        dist_file = Path(cmdline[-1]) / dist_filename
        if not dist_file.parent.is_dir():
            dist_file.parent.mkdir()
        dist_file.touch()
        return subprocess.CompletedProcess(
            args=(),
            returncode=0,
            stdout="",
            stderr="")

    s_run = mock.MagicMock(side_effect=create_dist_file)
    uid = 'xyz123'
    uid_obj = collections.namedtuple("uid_obj", "hex")(hex=uid)
    uid_dir = tmp_path / uid
    with mock.patch('subprocess.run', s_run):
        with mock.patch('uuid.uuid4', mock.MagicMock(return_value=uid_obj)):
            package_path = prepo.create_package(src_dir)
    args, kwargs = s_run.call_args
    assert args[0] == [sys.executable, str(setup_py_path), "sdist", "--dist-dir", str(uid_dir)]
    assert kwargs == {'check': False, 'stdout': subprocess.PIPE, 'stderr': subprocess.STDOUT}
    assert package_path == uid_dir / dist_filename
    assert package_path.exists()


@pytest.mark.parametrize("requirement, kind, package_info", [
    [
     "alpha==1.2.3", "requirement",
     PackageInfo("alpha",
                 version_specs=[VersionSpec(operator="==", version="1.2.3")]),
    ],

    [
     "alpha>=1.2.3,<5.1.*", "requirement",
     PackageInfo("alpha",
                 version_specs=[VersionSpec(operator=">=", version="1.2.3"),
                                VersionSpec(operator="<", version="5.1.*")]),
    ],

    [
     "./alpha-1.2.3.tar.gz", "package_path",
     PackageInfo("alpha",
                 version_specs=[VersionSpec(operator="===", version="1.2.3")]),
    ],

    [
     Path("alpha-1.2.3.tar.gz"), "package_path",
     PackageInfo("alpha",
                 version_specs=[VersionSpec(operator="===", version="1.2.3")]),
    ],

])
def test_PackageRepo_add_requirement(tmp_path, requirement, kind, package_info):
    prepo = PackageRepo(tmp_path)
    if kind == "package_path":
        cp_mock = mock.MagicMock(return_value=Path(requirement))
    else:
        cp_mock = mock.MagicMock(side_effect=ValueError(requirement))
    with mock.patch("bentobox.package_repo.PackageRepo.create_package", cp_mock):
        result = prepo.add_requirements([requirement])
    if kind == "package_path":
        assert cp_mock.call_count == 1
        args, kwargs = cp_mock.call_args
        assert cp_mock.call_args == ((requirement,), {})
    else:
        assert cp_mock.call_count == 0
    assert len(prepo) == 1
    assert prepo[package_info.name] == package_info
    assert list(prepo) == [package_info.name]
    assert list(prepo.values()) == [package_info]
    assert result == [package_info.name]


@pytest.mark.parametrize("requirements, package_infos, package_names", [
    [
     ["alpha==1.2.3", "./beta-2.3.4.tar.gz"],
     {'alpha': PackageInfo("alpha",
                           version_specs=[VersionSpec(operator="==", version="1.2.3")]),
      'beta': PackageInfo("beta",
                          version_specs=[VersionSpec(operator="===", version="2.3.4")]),
     },
     ["alpha", "beta"],
    ],

    [
     ["alpha>=1.2.3", "./beta-2.3.4.tar.gz", "alpha<=1.3.*"],
     {'alpha': PackageInfo("alpha",
                           version_specs=[VersionSpec(operator=">=", version="1.2.3"),
                                          VersionSpec(operator="<=", version="1.3.*")]),
      'beta': PackageInfo("beta",
                          version_specs=[VersionSpec(operator="===", version="2.3.4")]),
     },
     ["alpha", "beta"],
    ],
])
def test_PackageRepo_add_requirements(tmp_path, requirements, package_infos, package_names):
    prepo = PackageRepo(tmp_path)
    cp_mock = mock.MagicMock(side_effect=lambda req: Path(req))
    with mock.patch("bentobox.package_repo.PackageRepo.create_package", cp_mock):
        result = prepo.add_requirements(requirements)
    assert dict(prepo) == package_infos
    assert result == package_names
