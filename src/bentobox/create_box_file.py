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

from .util import load_box_module
from .env import DEFAULT_PYTHON_INTERPRETER, INIT_VENV_PACKAGES
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


def get_package_name(archive_path):
    """Get package name from archive path"""
    archive_path = Path(archive_path)
    archive_filename = archive_path.name
    match = re.search(r"(?P<name>.*?)-(?:\d+.*)", archive_filename)
    if not match:
        raise BoxInvalidPackageName(archive_path)
    dct = match.groupdict()
    return dct['name']


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
            print(result.stdout, file=sys.stderr)
            raise BoxCommandError("command {} failed".format(cmd))
        print("ERR: command {} failed:".format(cmd), file=sys.stderr)
        print(result.stdout, file=sys.stderr)
    return result.returncode


class PackageRepo:
    def __init__(self, tmpdir):
        self.tmpdir = tmpdir
        self.package_names = []
        self._seen_packages = set()
        self._pkg_data = []

    def create_package(self, package_path):
        if not package_path.exists():
            raise BoxPathError("path {} does not exist".format(package_path))
        tmpdir = self.tmpdir
        if package_path.is_file():
            yield package_path
        elif package_path.is_dir():
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
            for pkg_path in pkg_tmpdir.glob("*"):
                yield pkg_path

    def add_packages(self, packages):
        package_names = []
        seen_packages = self._seen_packages
        pkg_data = self._pkg_data
        for package in packages:
            if package in seen_packages:
                continue
            seen_packages.add(package)
            if {'/', '.'}.intersection(str(package)):
                for package_path in self.create_package(Path(package)):
                    package_name = get_package_name(package_path)
                    package_names.append(package_name)
                    pkg_data.append((package, package_name, package_path))
            else:
                package_names.append(package)
                pkg_data.append((package, package, None))
        self.package_names.extend(packages)
        return package_names

    def get_package_paths(self, download=True):
        package_paths = []
        if download:
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
            for package in self.package_names:
                cmdline.append(str(package))
            run_command(cmdline)
            for package_path in download_dir.glob("*"):
                if package_path.is_file():
                    package_name = get_package_name(package_path)
                    package_paths.append((package_name, package_path))
        else:
            for package, package_name, package_path in self._pkg_data:
                if package_path is not None:
                    package_paths.append((package_name, package_path))
        return package_paths


def create_box_file(box_name, output_path=None, mode=0o555, wrap_info=None,
                    packages=(), init_venv_packages=None,
                    pip_install_args=None, download=False,
                    update_shebang=True, check=True, freeze=True,
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
        iv_package_names = pkg_repo.add_packages(init_venv_packages)
        package_names = pkg_repo.add_packages(packages)

        package_paths = pkg_repo.get_package_paths(download=download)

        package_paths.sort(key=lambda x: x[1])
        package_paths.sort(key=lambda x: x[0])

        hash_placeholder = Hash().hexdigest()
        repo = collections.defaultdict(dict)
        for package_name, package_path in package_paths:
            repo[package_name][package_path.name] = hash_placeholder

        state = {
            "box_name": box_name,
            "python_interpreter": python_interpreter,
            "python_interpreter_orig": None,
            "install_dir": None,
            "wrap_mode": wrap_info.wrap_mode.name,
            "wraps": wrap_info.wraps,
            "freeze": freeze,
            "update_shebang": update_shebang,
            "verbose_level": int(verbose_level),
            "use_pypi": not download,
            "pip_install_args": pip_install_args,
            "init_venv_packages": iv_package_names,
            "packages": package_names,
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
