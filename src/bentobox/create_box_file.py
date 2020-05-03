"""
Create a box file
"""

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
from .env import DEFAULT_PYTHON_INTERPRETER
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


RE_BOX_NAME = re.compile(r"^\w+(?:\-\w+)*$")


def check_box_name(value):
    if not RE_BOX_NAME.match(value):
        raise BoxNameError(value)
    return value


def make_archives(tmpd, package_path):
    if not package_path.exists():
        raise BoxPathError("path {} does not exist".format(package_path))
    if package_path.is_file():
        yield package_path
    elif package_path.is_dir():
        setup_py_path = (package_path / "setup.py").resolve()
        if not setup_py_path.is_file():
            raise BoxPathError("path {} does not exist".format(package_path))
        tmpdir = Path(tmpd).joinpath(uuid.uuid4().hex)
        tmpdir.mkdir()
        old_cwd = Path.cwd()
        try:
            os.chdir(setup_py_path.parent)
            cmdline = [sys.executable, str(setup_py_path), "sdist", "--dist-dir", str(tmpdir)]
            result = subprocess.run(cmdline, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    check=False)
            clist = [cmdline[0]] + [shlex.quote(arg) for arg in cmdline[1:]]
            cmd = " ".join(clist)
            if result.returncode:
                raise BoxCommandError("command {} failed".format(cmd))
        finally:
            os.chdir(old_cwd)
        for archive_path in tmpdir.glob("*"):
            yield archive_path


def create_box_file(box_name, output_path=None, mode=0o555, wrap_info=None,
                    packages=(), pip_install_args=None,
                    update_shebang=True, check=True, freeze=True,
                    python_interpreter=DEFAULT_PYTHON_INTERPRETER,
                    force_overwrite=False, verbose_level=1, debug=False):
    # pylint: disable=too-many-arguments
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
        if pip_install_args is None:
            pip_install_args = []

        template = box_file.__file__

        if not output_path.parent.exists():
            output_path.parent.mkdir(parents=True)

        hash_placeholder = Hash().hexdigest()
        packages_data = []
        archives = []
        for package in packages:
            if {'/', '.'}.intersection(str(package)):
                for archive_path in make_archives(tmpd, Path(package)):
                    archive_name = archive_path.name
                    archive_index = len(packages_data)
                    packages_data.append({
                        'type': 'archive',
                        'name': archive_name,
                        'hash': hash_placeholder,
                    })
                    archives.append((archive_index, archive_path))
            else:
                packages_data.append({
                    'type': 'package',
                    'name': package,
                })

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
            "debug": bool(debug),
            "pip_install_args": pip_install_args,
            "packages": packages_data,
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
            f_out.write(box_file.MARK_ARCHIVES + '\n')
            hash_pos_list = []
            for archive_index, archive_path in archives:
                package_info = packages_data[archive_index]
                archive_name = package_info['name']
                f_out.write("#\n")
                f_out.write("#{}\n".format(archive_name))
                archive_hash_pos = f_out.tell()
                f_out.write("#{}\n".format(hash_placeholder))
                hashobj = Hash()
                with open(archive_path, "rb") as archive_file:
                    bsize = 70
                    while True:
                        data = archive_file.read(bsize)
                        if not data:
                            break
                        hashobj.update(data)
                        encoded_data = str(b64encode(data), 'utf-8')
                        f_out.write("#" + encoded_data + "\n")
                    f_out.flush()
                archive_hash = hashobj.hexdigest()
                packages_data[archive_index]['hash'] = archive_hash
                hash_pos_list.append((archive_hash_pos, archive_hash))
            # replace hash
            for pos, archive_hash in hash_pos_list:
                f_out.seek(pos)
                f_out.write("#{}".format(archive_hash))

        output_path.chmod(mode)
        box_file.replace_state(output_path, state)

        if check:
            check_box(output_path, Path(tmpd) / "bentobox_install_dir")


def check_box(box_path, install_dir=None):
    box_module = load_box_module(box_path)
    box_module.check(install_dir)  # pylint: disable=no-member
