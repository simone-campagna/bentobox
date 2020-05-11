from unittest import mock

import pytest

from bentobox.package_info import (
    VersionSpec,
    PackageInfo,
    BoxInvalidPackagePath,
    BoxInvalidRequirement,
)


def test_VersionSpec():
    spec = VersionSpec(operator="==", version="1.2.3")
    assert spec.operator == "=="
    assert spec.version == "1.2.3"
    assert str(spec) == "==1.2.3"


@pytest.mark.parametrize("package_path", [None, "/tmp/x-1.2.3.tar.gz"])
def test_PackageInfo(package_path):
    package_info = PackageInfo(
        name="alpha",
        version_specs=[
            VersionSpec('>=', '1.2.3'),
            VersionSpec('<', '2.0.0'),
            VersionSpec('~=', '1.5.*'),
        ],
    )
    assert package_info.name == 'alpha'
    assert len(package_info.version_specs) == 3
    assert str(package_info) == "alpha>=1.2.3,<2.0.0,~=1.5.*"


@pytest.mark.parametrize("package_path, result",  [
    ("alpha-1.2.3.tar.gz",
     PackageInfo(name="alpha",
                 version_specs=[VersionSpec(operator="===", version="1.2.3")])),
    ("alpha-beta-1.2.3.tar.gz",
     PackageInfo(name="alpha-beta",
                 version_specs=[VersionSpec(operator="===", version="1.2.3")])),
    ("alpha_beta-1.2.3.tar.gz",
     PackageInfo(name="alpha_beta",
                 version_specs=[VersionSpec(operator="===", version="1.2.3")])),
    ("alpha/beta-1.2.3.tar.gz",
     PackageInfo(name="beta",
                 version_specs=[VersionSpec(operator="===", version="1.2.3")])),
    ("./alpha-1.2.3.tar.gz",
     PackageInfo(name="alpha",
                 version_specs=[VersionSpec(operator="===", version="1.2.3")])),
    ("/tmp/uu345/alpha-1.2.3.tar.gz",
     PackageInfo(name="alpha",
                 version_specs=[VersionSpec(operator="===", version="1.2.3")])),
    ("alpha-1.2.3-py3-none-any.whl",
     PackageInfo(name="alpha",
                 version_specs=[VersionSpec(operator="===", version="1.2.3")])),
    ("alpha-1.2.3-py3.6.egg",
     PackageInfo(name="alpha",
                 version_specs=[VersionSpec(operator="===", version="1.2.3")])),
])
def test_PackageInfo_from_package_path(package_path, result):
    assert PackageInfo.from_package_path(package_path) == result


@pytest.mark.parametrize("package_path, error",  [
    ("alpha.tar.gz", BoxInvalidPackagePath('alpha.tar.gz')),
    ("alpha.1.2.3.tar.gz", BoxInvalidPackagePath('alpha.1.2.3.tar.gz')),
    ("alpha-a.2.3.tar.gz", BoxInvalidPackagePath('alpha-a.2.3.tar.gz')),
])
def test_PackageInfo_from_package_path_error(package_path, error):
    with pytest.raises(type(error)) as exc_info:
        PackageInfo.from_package_path(package_path)
    assert str(exc_info.value) == str(error)


@pytest.mark.parametrize("requirement, result",  [
    ("alpha", PackageInfo(name="alpha", version_specs=[])),
    ("alpha==1.2.3", PackageInfo(name="alpha", version_specs=[
        VersionSpec(operator="==", version="1.2.3")])),
    ("alpha>=1.2.3", PackageInfo(name="alpha", version_specs=[
        VersionSpec(operator=">=", version="1.2.3")])),
    ("alpha>1.2.3", PackageInfo(name="alpha", version_specs=[
        VersionSpec(operator=">", version="1.2.3")])),
    ("alpha<1.2.3", PackageInfo(name="alpha", version_specs=[
        VersionSpec(operator="<", version="1.2.3")])),
    ("alpha~=1.2.3", PackageInfo(name="alpha", version_specs=[
        VersionSpec(operator="~=", version="1.2.3")])),
    ("alpha!=1.2.3", PackageInfo(name="alpha", version_specs=[
        VersionSpec(operator="!=", version="1.2.3")])),
    ("alpha===a.b.c", PackageInfo(name="alpha", version_specs=[
        VersionSpec(operator="===", version="a.b.c")])),
    ("alpha>=1.2.3,<=1.8.0,~=1.5.*", PackageInfo(name="alpha", version_specs=[
        VersionSpec(operator=">=", version="1.2.3"),
        VersionSpec(operator="<=", version="1.8.0"),
        VersionSpec(operator="~=", version="1.5.*")])),
])
def test_PackageInfo_from_requirement(requirement, result):
    assert PackageInfo.from_requirement(requirement) == result


@pytest.mark.parametrize("requirement, error",  [
    ("==1.2.3", BoxInvalidRequirement("==1.2.3")),
    ("alpha.beta==1.2.3", BoxInvalidRequirement("'alpha.beta==1.2.3': invalid version spec '.beta==1.2.3'")),
    ("alpha=1.2.*", BoxInvalidRequirement("'alpha=1.2.*': invalid version spec '=1.2.*'")),
    ("alpha==1.2.*,", BoxInvalidRequirement("'alpha==1.2.*,': invalid version spec ''")),
    ("alpha==1.2.*,<", BoxInvalidRequirement("'alpha==1.2.*,<': invalid version spec '<'")),
    ("alpha==1.2.*<=1.3.*", BoxInvalidRequirement("'alpha==1.2.*<=1.3.*': invalid version spec '==1.2.*<=1.3.*'")),
    ("alpha==1.2.*,<=1.3.*,", BoxInvalidRequirement("'alpha==1.2.*,<=1.3.*,': invalid version spec ''")),
])
def test_PackageInfo_from_requirement_error(requirement, error):
    with pytest.raises(type(error)) as exc_info:
        PackageInfo.from_requirement(requirement)
    assert str(exc_info.value) == str(error)


@pytest.mark.parametrize("arg, fname", [
    ("alpha-1.2.3.tar.gz", 'requirement'),
    ("./alpha-1.2.3.tar.gz", 'package_path'),
    ("alpha", 'requirement'),
    (".alpha", 'requirement'),
    ("alpha.beta", 'requirement'),
    ("alpha/beta", 'package_path'),
    ("alpha==1.2.3", 'requirement'),
])
def test_PackageInfo_from_request_string(arg, fname):
    mmd = {
        'package_path': mock.MagicMock(),
        'requirement': mock.MagicMock(),
    }
    with mock.patch('bentobox.package_info.PackageInfo.from_package_path', mmd['package_path']):
        with mock.patch('bentobox.package_info.PackageInfo.from_requirement', mmd['requirement']):
            PackageInfo.from_request_string(arg)
    for key, mm in mmd.items():
        if key == fname:
            # assert mm.call_count == 1
            assert mm.call_args == ((arg,),)
        else:
            # assert mm.call_count == 0
            assert mm.call_args == None
