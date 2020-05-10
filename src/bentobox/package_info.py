"""
Package info
"""

import collections
import re

from pathlib import Path

import pkg_resources

from .errors import (
    BoxInvalidPackagePath,
    BoxInvalidRequirement,
)

__all__ = [
    'PackageInfo',
    'make_package_info',
    'make_package_info_from_path',
    'make_package_info_from_requirement',
]


PackageInfo = collections.namedtuple(  # pylint: disable=invalid-name
    "PackageInfo", "name version")


def make_package_info(package):
    if isinstance(package, Path) or '/' in package:
        return make_package_info_from_path(package)
    return make_package_info_from_requirement(package)


def make_package_info_from_path(package_path):
    """Make package info from package path

       >>> make_package_info_from_path('alpha-1.2.3.tar.gz')
       PackageInfo(name='alpha', version='1.2.3')
       >>> make_package_info_from_path('alpha-1.2.3-py3-none-any.whl')
       PackageInfo(name='alpha', version='1.2.3')

       Paramenters
       -----------
       requirement: str
           requirement specification

       Returns
       -------
       PackageInfo
           the package info object
    """
    package_path = Path(package_path)
    package_filename = package_path.name
    if package_path.suffix == ".egg":
        dist = pkg_resources.Distribution.from_location(None, package_filename)
        name = dist.project_name
        version = dist.version
    else:
        regex = r"(?P<name>.*?)-(?P<version>\d+(?:\.\d+)+)(?:.*)$"
        match = re.search(regex, package_filename)
        if not match:
            raise BoxInvalidPackagePath(package_path)
        dct = match.groupdict()
        name = dct['name']
        version = dct['version']
    return PackageInfo(name=name, version=version)


def make_package_info_from_requirement(requirement):
    """Make package info from requirement specification

       >>> make_package_info_from_requirement('alpha')
       PackageInfo(name='alpha', version=None)
       >>> make_package_info_from_requirement('alpha==1.2.3')
       PackageInfo(name='alpha', version='1.2.3')
       >>> make_package_info_from_requirement('alpha>=1.2.3')
       PackageInfo(name='alpha', version='1.2.3')
       >>> make_package_info_from_requirement('alpha>1.2.3')
       PackageInfo(name='alpha', version=None)

       Paramenters
       -----------
       requirement: str
           requirement specification

       Returns
       -------
       PackageInfo
           the package info object
    """
    r_version_spec = re.compile(
        r"(?P<name>[\w\-]+)(?:(?P<operator>===|==|~=|!=|<=|>=|<|>)(?P<version>.*))?$")
    match = r_version_spec.match(requirement)
    if not match:
        raise BoxInvalidRequirement(requirement)
    name = match.group('name')
    operator = match.group('operator')
    if operator == "===":
        version = match.group('version')
    elif operator in {'==', '>=', '~='}:
        version = match.group('version')
        r_version = re.compile(r"\w+(\.\w+)*$")
        if not r_version.match(version):
            raise BoxInvalidRequirement(requirement)
    else:
        version = None
    return PackageInfo(name=name, version=version)
