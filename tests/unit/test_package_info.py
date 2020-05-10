import pytest

from bentobox.package_info import (
    PackageInfo,
    make_package_info_from_path,
    make_package_info_from_requirement,
    make_package_info,
)
from bentobox.errors import (
    BoxInvalidPackagePath,
    BoxInvalidRequirement,
)


@pytest.mark.parametrize("package_path, result",  [
    ("alpha-1.2.3.tar.gz", PackageInfo(name="alpha", version="1.2.3")),
    ("alpha-beta-1.2.3.tar.gz", PackageInfo(name="alpha-beta", version="1.2.3")),
    ("alpha_beta-1.2.3.tar.gz", PackageInfo(name="alpha_beta", version="1.2.3")),
    ("alpha/beta-1.2.3.tar.gz", PackageInfo(name="beta", version="1.2.3")),
    ("./alpha-1.2.3.tar.gz", PackageInfo(name="alpha", version="1.2.3")),
    ("/tmp/uu345/alpha-1.2.3.tar.gz", PackageInfo(name="alpha", version="1.2.3")),
    ("alpha-1.2.3-py3-none-any.whl", PackageInfo(name="alpha", version="1.2.3")),
])
def test_make_package_info_from_path(package_path, result):
    assert make_package_info_from_path(package_path) == result


@pytest.mark.parametrize("package_path, error",  [
    ("alpha.tar.gz", BoxInvalidPackagePath('alpha.tar.gz')),
    ("alpha.1.2.3.tar.gz", BoxInvalidPackagePath('alpha.1.2.3.tar.gz')),
    ("alpha-a.2.3.tar.gz", BoxInvalidPackagePath('alpha-a.2.3.tar.gz')),
])
def test_make_package_info_from_path_error(package_path, error):
    with pytest.raises(type(error)) as exc_info:
        make_package_info_from_path(package_path)
    assert str(exc_info.value) == str(error)


@pytest.mark.parametrize("requirement, result",  [
    ("alpha", PackageInfo(name="alpha", version=None)),
    ("alpha==1.2.3", PackageInfo(name="alpha", version="1.2.3")),
    ("alpha>=1.2.3", PackageInfo(name="alpha", version="1.2.3")),
    ("alpha>1.2.3", PackageInfo(name="alpha", version=None)),
    ("alpha<1.2.3", PackageInfo(name="alpha", version=None)),
    ("alpha~=1.2.3", PackageInfo(name="alpha", version="1.2.3")),
    ("alpha===a.b.c", PackageInfo(name="alpha", version="a.b.c")),
])
def test_make_package_info_from_requirement(requirement, result):
    assert make_package_info_from_requirement(requirement) == result


@pytest.mark.parametrize("requirement, error",  [
    ("alpha.xx==a.b-c", BoxInvalidRequirement("alpha.xx==a.b-c")),
    ("alpha==1.2.*", BoxInvalidRequirement("alpha==1.2.*")),
])
def test_make_package_info_from_requirement_error(requirement, error):
    with pytest.raises(type(error)) as exc_info:
        make_package_info_from_requirement(requirement)
    assert str(exc_info.value) == str(error)
