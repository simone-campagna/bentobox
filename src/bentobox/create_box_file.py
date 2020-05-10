"""
Create a box file
"""

import collections
import hashlib
import os
import re
import shlex
import subprocess
import sys
import tempfile
import uuid
from base64 import b64encode
from pathlib import Path

import pkg_resources

from .util import load_box_module
from .env import (
    DEFAULT_PYTHON_INTERPRETER,
    INIT_VENV_PACKAGES,
    BENTOBOX_VERSION,
    BOX_FILE_VERSION,
)
from . import box_file


__all__ = [
    'BoxCreateError',
    'BoxNameError',
    'BoxPathError',
    'BoxCommandError',
    'BoxFileError',
    'check_box_name',
    'create_box_file',
]


Hash = hashlib.sha1


class BoxCreateError(ValueError):
    pass


class BoxNameError(BoxCreateError):
    pass


class BoxPathError(BoxCreateError):
    pass


class BoxCommandError(BoxCreateError):
    pass


class BoxFileError(BoxCreateError):
    pass


class BoxInvalidPackageName(BoxCreateError):
    pass


RE_BOX_NAME = re.compile(r"^\w+(?:\-\w+)*$")


PackageInfo = collections.namedtuple(  # pylint: disable=invalid-name
    "PackageInfo", "name version")


PackageRequest = collections.namedtuple(  # pylint: disable=invalid-name
    "PackageRequest", "info request path")


def make_package_request(package_info, package_path):
    if package_info.version:
        request_fmt = "{p.name}=={p.version}"
    else:
        request_fmt = "{p.name}"
    return PackageRequest(
        info=package_info,
        path=package_path,
        request=request_fmt.format(p=package_info))


def get_package_info_from_path(archive_path):
    """Get package name from archive path"""
    archive_path = Path(archive_path)
    archive_filename = archive_path.name
    if archive_path.suffix == ".egg":
        dist = pkg_resources.Distribution.from_location(None, archive_filename)
        name = dist.project_name
        version = dist.version
    else:
        regex = r"(?P<name>.*?)-(?P<version>\d+(?:\.\d+)+)(?:.*)"
        match = re.search(regex, archive_filename)
        if not match:
            raise BoxInvalidPackageName(archive_path)
        dct = match.groupdict()
        name = dct['name']
        version = dct['version']
    return PackageInfo(name=name, version=version)


def get_package_info_from_requirement(requirement):
    r_version_spec = re.compile(r"(?:==|~=|!=|<=|>=|<|>|===)")
    lst = r_version_spec.split(requirement, maxsplit=1)
    name, version = lst[0], None
    if len(lst) > 1:
        version = lst[1]
    return PackageInfo(name=name, version=version)


def get_package_info(package):
    if isinstance(package, Path) or '/' in package:
        return get_package_info_from_path(package)
    return get_package_info_from_requirement(package)


def check_box_name(value):
    if not RE_BOX_NAME.match(value):
        raise BoxNameError(value)
    return value


def run_command(cmdline, raising=True):
    result = subprocess.run(cmdline, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            check=False)
    clist = [cmdline[0]] + [shlex.quote(arg) for arg in cmdline[1:]]
    # if True:
    #     cmd = " ".join(clist)
    #     print("$ {}".format(cmd), file=sys.stderr)
    #     print(result.stdout, file=sys.stderr)
    if result.returncode:
        cmd = " ".join(clist)
        if raising:
            print("$ {}".format(cmd), file=sys.stderr)
            print(str(result.stdout, 'utf-8'), file=sys.stderr)
            raise BoxCommandError("command {} failed".format(cmd))
        print("ERR: command {} failed:".format(cmd), file=sys.stderr)
        print(str(result.stdout, 'utf-8'), file=sys.stderr)
    return result.returncode


class PackageRepo:
    def __init__(self, tmpdir):
        self.tmpdir = tmpdir
        self._pkgrequests = {}

    def create_package(self, package_path):
        if not package_path.exists():
            raise BoxPathError("path {} does not exist".format(package_path))
        tmpdir = self.tmpdir
        if package_path.is_file():
            return package_path
        else:
            setup_py_path = (package_path / "setup.py").resolve()
            if not setup_py_path.is_file():
                raise BoxPathError("path {} does not exist".format(package_path))
            pkg_tmpdir = tmpdir / uuid.uuid4().hex
            pkg_tmpdir.mkdir()
            old_cwd = Path.cwd()
            try:
                os.chdir(setup_py_path.parent)
                cmdline = [sys.executable, str(setup_py_path), "sdist",
                           "--dist-dir", str(pkg_tmpdir)]
                run_command(cmdline)
            finally:
                os.chdir(old_cwd)
            dists = list(pkg_tmpdir.glob("*"))
            if not dists:
                raise BoxPathError("path {}: dist file not found".format(package_path))
            if len(dists) != 1:
                raise BoxPathError("path {}: too many dist files found".format(package_path))
            return dists[0]

    def add_requirements(self, requirements):
        pkgrequest = self._pkgrequests
        package_names = []
        for requirement in requirements:
            if '/' in str(requirement):
                package_path = self.create_package(Path(requirement))
                package_info = get_package_info_from_path(package_path)
            else:
                package_path = None
                package_info = get_package_info_from_requirement(requirement)
            package_names.append(package_info.name)
            pkgrequest[package_info.name] = make_package_request(
                package_info=package_info,
                package_path=package_path)
        return package_names

    def get_requirements(self, package_names):
        pkgrequest = self._pkgrequests
        requirements = []
        for package_name in package_names:
            requirements.append(pkgrequest[package_name].request)
        return requirements

    def get_package_paths(self, freeze_pypi=True):
        package_paths = []
        if freeze_pypi:
            pip_dir = self.tmpdir / 'pip-{}'.format(uuid.uuid4().hex)
            download_dir = pip_dir / 'downloads'
            build_dir = pip_dir / 'build'
            src_dir = pip_dir / 'src'
            for ddir in download_dir, build_dir, src_dir:
                if not ddir.is_dir():
                    ddir.mkdir(parents=True)
            cmdline = [
                'pip', 'download',
                '--only-binary', ':all:',
                '--dest', str(download_dir),
                '--build', str(build_dir),
                '--src', str(src_dir),
                '--platform', 'any',
                '--python-version', '3',
                '--implementation', 'py',
                '--abi', 'none',
            ]
            for package_request in self._pkgrequests.values():
                if package_request.path:
                    cmdline.append(str(package_request.path))
                else:
                    cmdline.append(package_request.request)
            run_command(cmdline)
            for package_path in download_dir.glob("*"):
                if package_path.is_file():
                    package_info = get_package_info_from_path(package_path)
                    package_paths.append((package_info.name, package_path))
        else:
            for package_name, package_request in self._pkgrequests.items():
                if package_request.path is not None:
                    package_paths.append((package_name, package_request.path))
        return package_paths


def create_box_file(box_name, output_path=None, mode=0o555, wrap_info=None,
                    packages=(), init_venv_packages=None,
                    pip_install_args=None, update_shebang=True, check=True,
                    freeze_env=True, freeze_pypi=True,
                    python_interpreter=DEFAULT_PYTHON_INTERPRETER,
                    force_overwrite=False, verbose_level=1):
    # pylint: disable=too-many-arguments
    if init_venv_packages is None:
        init_venv_packages = INIT_VENV_PACKAGES
    if wrap_info is None:
        wrap_info = box_file.WrapInfo(box_file.WrapMode.NONE, None)
    box_name = check_box_name(box_name)
    if output_path is None:
        output_path = Path(box_name).resolve()
    else:
        output_path = Path(output_path).resolve()
    if output_path.exists():
        if force_overwrite:
            output_path.unlink()
        else:
            raise BoxFileError("file {!r} already exists".format(str(output_path)))

    with tempfile.TemporaryDirectory() as tmpd:
        tmpdir = Path(tmpd)

        if pip_install_args is None:
            pip_install_args = []

        template = box_file.__file__

        if not output_path.parent.exists():
            output_path.parent.mkdir(parents=True)


        pkg_repo = PackageRepo(tmpdir=tmpdir)
        init_package_names = pkg_repo.add_requirements(init_venv_packages)
        user_package_names = pkg_repo.add_requirements(packages)

        package_paths = pkg_repo.get_package_paths(freeze_pypi=freeze_pypi)

        package_paths.sort(key=lambda x: x[1])
        package_paths.sort(key=lambda x: x[0])

        init_packages = pkg_repo.get_requirements(init_package_names)
        user_packages = pkg_repo.get_requirements(user_package_names)

        hash_placeholder = Hash().hexdigest()
        repo = collections.defaultdict(dict)
        for package_name, package_path in package_paths:
            repo[package_name][package_path.name] = hash_placeholder

        state = {
            "version": BENTOBOX_VERSION,
            "box_file_version": BOX_FILE_VERSION,
            "box_name": box_name,
            "python_interpreter": python_interpreter,
            "install_dir": box_file.default_install_dir(box_name),
            "orig": {
                "install_dir": None,
                "python_interpreter": None,
            },
            "wrap_mode": wrap_info.wrap_mode.name,
            "wraps": wrap_info.wraps,
            "freeze_env": freeze_env,
            "use_pypi": not freeze_pypi,
            "update_shebang": update_shebang,
            "verbose_level": int(verbose_level),
            "pip_install_args": pip_install_args,
            "init_venv_packages": init_packages,
            "packages": user_packages,
            "repo": repo,
        }

        with open(output_path, "w+") as f_out, open(template, "r") as f_in:
            f_out.write(box_file.create_header(state, fill_len=box_file.HEADER_FILL_LEN))
            status = 'skip'
            for line in f_in:
                if status == 'skip':
                    if line.startswith(box_file.MARK_END_OF_HEADER):
                        f_out.write(line)
                        status = 'copy'
                elif status == 'copy':
                    f_out.write(line)
                    if line.startswith(box_file.MARK_END_OF_SOURCE):
                        break
            f_out.write(box_file.MARK_REPO + '\n')
            hash_pos_list = []
            for package_name, package_path in package_paths:
                f_out.write("#\n")
                f_out.write("#{}\n".format(package_name))
                f_out.write("#{}\n".format(package_path.name))
                package_hash_pos = f_out.tell()
                f_out.write("#{}\n".format(hash_placeholder))
                hashobj = Hash()
                with open(package_path, "rb") as package_file:
                    bsize = 70
                    while True:
                        data = package_file.read(bsize)
                        if not data:
                            break
                        hashobj.update(data)
                        encoded_data = str(b64encode(data), 'utf-8')
                        f_out.write("#" + encoded_data + "\n")
                    f_out.flush()
                package_hash = hashobj.hexdigest()
                repo[package_name][package_path.name] = package_hash
                hash_pos_list.append((package_hash_pos, package_hash))
            # replace hash
            for pos, package_hash in hash_pos_list:
                f_out.seek(pos)
                f_out.write("#{}".format(package_hash))

        output_path.chmod(mode)
        box_file.replace_state(output_path, state)

        if check:
            check_box(output_path, tmpdir / "bentobox_install_dir")


def check_box(box_path, install_dir=None):
    box_module = load_box_module(box_path)
    box_module.check(install_dir)  # pylint: disable=no-member
