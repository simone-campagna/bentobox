"""
Package repo
"""

import collections.abc
import os
import sys
import uuid
from pathlib import Path

from . import box_file
from .env import DEFAULT_PYPI_INDEX_URL
from .errors import BoxPathError
from .package_info import PackageInfo
from .util import run_command


__all__ = [
    'PackageRepo',
]


class PackageRepo(collections.abc.Mapping):
    """Package repository - download packages"""

    def __init__(self, workdir):
        self.workdir = Path(workdir)
        self._pkginfo = {}
        self._pkgpaths = []

    def __getitem__(self, name):
        return self._pkginfo[name]

    def __iter__(self):
        yield from self._pkginfo

    def __len__(self):
        return len(self._pkginfo)

    def create_package(self, package_path):
        """Create a package distribution from a package_path

           Parameters
           ----------
           package_path: str or Path
               a package distribution file, for instance ./alpha-1.2.3.tar.gz,
               or a python source dir containing a setup.py file

           Returns
           -------
           Path
               a package path

           Raises
           ------
           BoxPathError
               if a package_path does not exist
        """
        package_path = Path(package_path)
        if not package_path.exists():
            raise BoxPathError("path {} does not exist".format(package_path))
        workdir = self.workdir
        if package_path.is_file():
            return package_path
        else:
            setup_py_path = (package_path / "setup.py").resolve()
            if not setup_py_path.is_file():
                raise BoxPathError("path {} does not exist".format(setup_py_path))
            pkg_workdir = workdir / uuid.uuid4().hex
            pkg_workdir.mkdir()
            old_cwd = Path.cwd()
            try:
                os.chdir(setup_py_path.parent)
                cmdline = [sys.executable, str(setup_py_path), "sdist",
                           "--dist-dir", str(pkg_workdir)]
                run_command(cmdline)
            finally:
                os.chdir(old_cwd)
            dists = list(pkg_workdir.glob("*"))
            if not dists:
                raise BoxPathError("path {}: dist file not found".format(package_path))
            if len(dists) != 1:
                raise BoxPathError("path {}: too many dist files found".format(package_path))
            return dists[0]

    def add_requirements(self, requirements):
        """Add requirements

           Parameters
           ----------
           requirements: list
               a list of requirements, such as
                   alpha>=1.2.0,<2.0.0
                   ./alpha-1.2.3.tar.gz

           Returns
           -------
           package_names
               a list of package names

           Raises
           ------
           BoxPathError
               if a package_path does not exist
        """
        pkginfo = self._pkginfo
        pkgpaths = self._pkgpaths
        package_names = []
        for requirement in requirements:
            if isinstance(requirement, Path) or '/' in str(requirement):
                package_path = self.create_package(requirement)
                package_info = PackageInfo.from_package_path(package_path)
            else:
                package_path = None
                package_info = PackageInfo.from_requirement(requirement)
            pname = package_info.name
            if package_path is not None:
                pkgpaths.append((pname, package_path))
            if pname not in package_names:
                package_names.append(pname)
            if pname in pkginfo:
                pkginfo[pname] = pkginfo[pname]._replace(
                    version_specs=pkginfo[pname].version_specs + package_info.version_specs)
            else:
                pkginfo[pname] = package_info
        return package_names

    def get_requirements(self, package_names):
        pkginfo = self._pkginfo
        requirements = []
        for package_name in package_names:
            requirements.append(str(pkginfo[package_name]))
        return requirements

    def get_package_paths(self, freeze_pypi=True):
        pip_dir = self.workdir / 'pip-{}'.format(uuid.uuid4().hex)
        pip_args = []
        if self._pkgpaths:
            pip_repo_dir = pip_dir / "repo"
            if not pip_repo_dir.exists():
                pip_repo_dir.mkdir(parents=True)
            package_files = []
            for package_name, package_path in self._pkgpaths:
                package_link = pip_repo_dir / package_path.name
                package_link.symlink_to(package_path.resolve())
                package_files.append((package_name, package_link.name))
            pip_index_dir = box_file.build_pypi_index(pip_repo_dir, package_files)
            pip_args.append('--index-url=file://{}'.format(pip_index_dir))
            pip_args.append('--extra-index-url={}'.format(DEFAULT_PYPI_INDEX_URL))
        package_paths = []
        if freeze_pypi:
            download_dir = pip_dir / 'downloads'
            build_dir = pip_dir / 'build'
            src_dir = pip_dir / 'src'
            for ddir in download_dir, build_dir, src_dir:
                if not ddir.is_dir():
                    ddir.mkdir(parents=True)
            cmdline = [
                'pip', 'download',
                '--dest', str(download_dir),
                '--build', str(build_dir),
                '--src', str(src_dir),
                # '--only-binary', ':all:',
                # '--platform', 'any',
                # '--python-version', '36',
                # '--implementation', 'py',
                # '--abi', 'none',
            ]
            cmdline.extend(pip_args)
            for package_info in self._pkginfo.values():
                cmdline.append(str(package_info))
            run_command(cmdline)
            for package_path in download_dir.glob("*"):
                if package_path.is_file():
                    package_info = PackageInfo.from_package_path(package_path)
                    package_paths.append((package_info.name, package_path))
        else:
            package_paths = self._pkgpaths[:]
        return package_paths
