"""
Package info
"""

import collections
import re

from pathlib import Path

import pkg_resources

from .errors import (
    BoxInvalidVersionSpec,
    BoxInvalidPackagePath,
    BoxInvalidRequirement,


)

__all__ = [
    'VersionSpec',
    'PackageInfo',
]


class VersionSpec(collections.namedtuple("_VersionSpec", "operator version")):
    __re__ = re.compile(
        r"^\s*(?P<operator>===|==|~=|!=|<=|>=|<|>)\s*(?P<version>[^\,\=\~\<\>\!]+)\s*$"
    )

    def __str__(self):
        return ''.join(self)

    @classmethod
    def from_spec_string(cls, spec_string):
        """Make VersionSpec from string

           >>> VersionSpec.from_spec_string('==1.2.3')
           VersionSpec(operator='==', version='1.2.3')

           Parameters
           ----------
           spec_string: str
               the version spec string

           Returns
           -------
           VersionSpec
               the VersionSpec instance

           Raises
           ------
               BoxInvalidVersionSpec
        """
        match = cls.__re__.match(spec_string)
        if not match:
            raise BoxInvalidVersionSpec(spec_string)
        return cls(operator=match.group('operator'), version=match.group('version'))


class PackageInfo(collections.namedtuple("_PackageInfo", "name path version_specs")):
    def __str__(self):
        return '{}{}'.format(
            self.name,
            ','.join(str(spec) for spec in self.version_specs))

    @classmethod
    def from_package_path(cls, package_path):
        """Make package info from package path

           >>> PackageInfo.from_package_path('alpha-1.2.3.tar.gz')  #doctest: +ELLIPSIS
           PackageInfo(name='alpha', path='alpha-1.2.3.tar.gz', version_specs=[...])
           >>> PackageInfo.from_package_path('alpha-1.2.3-py3-none-any.whl')  #doctest: +ELLIPSIS
           PackageInfo(name='alpha', path='alpha-1.2.3-py3-none-any.whl', version_specs=[...])
           >>> PackageInfo.from_package_path('alpha-1.2.3-py3.6.egg')  #doctest: +ELLIPSIS
           PackageInfo(name='alpha', path='alpha-1.2.3-py3.6.egg', version_specs=[...])

           Paramenters
           -----------
           requirement: str
               requirement specification

           Returns
           -------
           PackageInfo
               the package info instance

           Raises
           ------
           BoxInvalidPackagePath
        """
        pkg_path = Path(package_path)
        pkg_filename = pkg_path.name
        if pkg_path.suffix == ".egg":
            dist = pkg_resources.Distribution.from_location(None, pkg_filename)
            name = dist.project_name
            version = dist.version
        else:
            regex = r"(?P<name>[\w\-]+)-(?P<version>\d+(?:\.\d+)+)(?:.*)$"
            match = re.search(regex, pkg_filename)
            if not match:
                raise BoxInvalidPackagePath(package_path)
            dct = match.groupdict()
            name = dct['name']
            version = dct['version']
        return cls(
            name=name,
            path=package_path,
            version_specs=[VersionSpec(operator='===', version=version)])

    @classmethod
    def from_requirement(cls, requirement):
        """Make package info from requirement specification

           >>> PackageInfo.from_requirement('alpha')
           PackageInfo(name='alpha', path=None, version_specs=[])
           >>> PackageInfo.from_requirement('alpha==1.2.3')  #doctest: +ELLIPSIS
           PackageInfo(name='alpha', path=None, version_specs=[...])
           >>> PackageInfo.from_requirement('alpha>1.2.3')  #doctest: +ELLIPSIS
           PackageInfo(name='alpha', path=None, version_specs=[...])

           Paramenters
           -----------
           requirement: str
               requirement specification

           Returns
           -------
           PackageInfo
               the package info object

           Raises
           ------
           BoxInvalidRequirement
        """
        r_name_rest = re.compile(
            r"^(?P<name>[\w\-]+)(?P<rest>.*)$"
        )
        match = r_name_rest.search(requirement)
        if match:
            version_specs = []
            name = match.group('name')
            version_specs = []
            rest = match.group('rest').strip()
            if rest:
                spec_strings = rest.split(',')
                for spec_string in spec_strings:
                    try:
                        version_spec = VersionSpec.from_spec_string(spec_string)
                    except BoxInvalidVersionSpec as err:
                        raise BoxInvalidRequirement(
                            "{!r}: invalid version spec {!r}".format(requirement, spec_string)
                        ) from err
                    version_specs.append(version_spec)
        else:
            raise BoxInvalidRequirement(requirement)
        return cls(
            name=name,
            path=None,
            version_specs=version_specs)

    @classmethod
    def from_request_string(cls, request_string):
        """Make PackageInfo from a request string (requirement or package path)

           >>> PackageInfo.from_request_string('alpha')
           PackageInfo(name='alpha', path=None, version_specs=[])
           >>> PackageInfo.from_request_string('alpha==1.2.3')  #doctest: +ELLIPSIS
           PackageInfo(name='alpha', path=None, version_specs=[...])
           >>> PackageInfo.from_request_string('./alpha-1.2.3.tar.gz')  #doctest: +ELLIPSIS
           PackageInfo(name='alpha', path='./alpha-1.2.3.tar.gz', version_specs=[...])
           >>> PackageInfo.from_request_string('alpha-1.2.3.tar.gz')  #doctest: +ELLIPSIS
           Traceback (most recent call last):
            ...
           bentobox.errors.BoxInvalidRequirement: '...': invalid version spec '.2.3.tar.gz'
           >>> PackageInfo.from_request_string('./alpha==1.2.3')
           Traceback (most recent call last):
            ...
           bentobox.errors.BoxInvalidPackagePath: ./alpha==1.2.3

           Paramenters
           -----------
           request_string: str
               a requirement specification or a package path containing a '/'

           Returns
           -------
           PackageInfo
               the package info object

           Raises
           ------
           BoxInvalidRequirement
           BoxInvalidPackagePath
        """
        if isinstance(request_string, Path) or '/' in request_string:
            meth = cls.from_package_path
        else:
            meth = cls.from_requirement
        return meth(request_string)
