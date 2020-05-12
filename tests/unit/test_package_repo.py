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


def test_PackageRepo_create_packages_from_path_err_missing(tmp_path):
    dist_file = tmp_path / "alpha-1.2.3.tar.gz"
    prepo = PackageRepo(tmp_path)
    print("::::", dist_file, dist_file.exists())
    with pytest.raises(BoxPathError) as exc_info:
        prepo.create_packages(dist_file)
    assert str(exc_info.value) == str(BoxPathError("path {} does not exist".format(dist_file)))
    

def test_PackageRepo_create_packages_from_file(tmp_path):
    dist_file = tmp_path / "alpha-1.2.3.tar.gz"
    dist_file.touch()
    prepo = PackageRepo(tmp_path)
    pname = "alpha-1.2.3-py3-none-any.whl"
    def create_wheel(cmdline, *args, **kwargs):
        pdir = Path(cmdline[-2])
        ppack = Path(cmdline[-1])
        pwheel = pdir / pname
        pwheel.touch()
        return subprocess.CompletedProcess(
            args=(),
            returncode=0,
            stdout="",
            stderr="")
    s_run = mock.MagicMock(side_effect=create_wheel)
    uid = 'xyz123'
    uid_obj = collections.namedtuple("uid_obj", "hex")(hex=uid)
    uid_dir = tmp_path / uid
    with mock.patch('subprocess.run', s_run):
        with mock.patch('uuid.uuid4', mock.MagicMock(return_value=uid_obj)):
            assert [x.name for x in prepo.create_packages(dist_file)] == [pname]
    args, kwargs = s_run.call_args
    assert args[0] == ["pip", "wheel", "--no-deps", "--only-binary", ":all:",
                       "--wheel-dir", str(uid_dir), str(dist_file)]
    assert kwargs == {'check': False, 'stdout': subprocess.PIPE, 'stderr': subprocess.STDOUT}


def test_PackageRepo_create_packages_from_dir(tmp_path, examples_dir):
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
        dist_file = Path(cmdline[-2]) / dist_filename
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
            package_paths = prepo.create_packages(src_dir)
    args, kwargs = s_run.call_args
    assert args[0] == ["pip", "wheel", "--no-deps", "--only-binary", ":all:",
                       "--wheel-dir", str(uid_dir), str(src_dir)]
    assert kwargs == {'check': False, 'stdout': subprocess.PIPE, 'stderr': subprocess.STDOUT}
    assert package_paths == [uid_dir / dist_filename]
    for package_path in package_paths:
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
        cp_mock = mock.MagicMock(return_value=[Path(requirement)])
    else:
        cp_mock = mock.MagicMock(side_effect=ValueError(requirement))
    with mock.patch("bentobox.package_repo.PackageRepo.create_packages", cp_mock):
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
    def create_wheels(arg):
        return [Path(arg)]
    cp_mock = mock.MagicMock(side_effect=create_wheels)
    with mock.patch("bentobox.package_repo.PackageRepo.create_packages", cp_mock):
        result = prepo.add_requirements(requirements)
    assert dict(prepo) == package_infos
    assert result == package_names


def test_PackageRepo_get_requirements(tmp_path):
    prepo = PackageRepo(tmp_path)
    package_names = prepo.add_requirements(["alpha>=0.2,<1.0", "beta==1.2", "alpha!=0.6"])
    assert package_names == ['alpha', 'beta']
    reqs = prepo.get_requirements(package_names)
    assert reqs == ["alpha>=0.2,<1.0,!=0.6", "beta==1.2"]


@pytest.mark.parametrize("freeze_pypi", [True, False])
def test_PackageRepo_get_package_paths_empty(tmp_path, freeze_pypi):
    prepo = PackageRepo(tmp_path)
    assert prepo.get_package_paths() == []


def test_PackageRepo_get_package_paths_no_freeze_pypi(tmp_path):
    prepo = PackageRepo(tmp_path)
    alpha_path = tmp_path / "alpha-1.2.3-py3-none-any.whl"
    beta_path = tmp_path / "beta-2.3.4-py3-none-any.whl"
    gamma_path = tmp_path / "gamma-3.4.5-py3-none-any.whl"
    outputs = [
        [beta_path],
    ]
    cp_mock = mock.MagicMock(side_effect=outputs)
    with mock.patch("bentobox.package_repo.PackageRepo.create_packages", cp_mock):
        package_names = prepo.add_requirements(["alpha==1.2.3", "./beta-2.3.4.tar.gz"])
        assert package_names == ["alpha", "beta"]
        package_names = prepo.add_requirements(["gamma==3.4.5"])
        assert package_names == ["gamma"]
    paths = prepo.get_package_paths(freeze_pypi=False)
    assert paths == [('beta', beta_path)]


def test_PackageRepo_get_package_paths_freeze_pypi(tmp_path):
    prepo = PackageRepo(tmp_path)
    alpha_path = tmp_path / "alpha-1.2.3-py3-none-any.whl"
    beta_path = tmp_path / "beta-2.3.4-py3-none-any.whl"
    gamma_path = tmp_path / "gamma-3.4.5-py3-none-any.whl"
    outputs = [
        [beta_path],
    ]
    cp_mock = mock.MagicMock(side_effect=outputs)
    with mock.patch("bentobox.package_repo.PackageRepo.create_packages", cp_mock):
        package_names = prepo.add_requirements(["alpha==1.2.3", "./beta-2.3.4.tar.gz"])
        assert package_names == ["alpha", "beta"]
        package_names = prepo.add_requirements(["gamma==3.4.5"])
        assert package_names == ["gamma"]

    requirements = prepo.get_requirements(['alpha', 'beta', 'gamma'])
    assert requirements == ["alpha==1.2.3", "beta===2.3.4", "gamma==3.4.5"]

    uid = 'xyz123'
    uid_obj = collections.namedtuple("uid_obj", "hex")(hex=uid)
    uid_dir = tmp_path / ("pip-" + uid)

    repo_dir = uid_dir / "repo"
    repo_dir.mkdir(parents=True)  # to cover existing directory check

    dld_dir = uid_dir / "downloads"
    built_alpha_path = dld_dir / "alpha-1.2.3-py3-none-any.whl"
    built_beta_path = dld_dir / "beta-2.3.4-py3-none-any.whl"
    built_gamma_path = dld_dir / "gamma-3.4.5-py3-none-any.whl"
    built_delta_path = dld_dir / "delta-4.5.6-py3-none-any.whl"
    fake_dir = dld_dir / "downloads" / "fake-1.2.3.tar.gz"
    def runc(cmdline, *args, **kwargs):
        built_alpha_path.touch()
        built_beta_path.touch()
        built_gamma_path.touch()
        built_delta_path.touch()
        fake_dir.mkdir(parents=True)  # to cover directory skip
        return 0

        
    rc_mock = mock.MagicMock(side_effect=runc)
    with mock.patch("bentobox.package_repo.run_command", rc_mock):
        with mock.patch('uuid.uuid4', mock.MagicMock(return_value=uid_obj)):
            paths = prepo.get_package_paths(freeze_pypi=True)
    assert set(paths) == {
        ('alpha', built_alpha_path),
        ('beta', built_beta_path),
        ('gamma', built_gamma_path),
        ('delta', built_delta_path),
    }
