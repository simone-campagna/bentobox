"""
Create a box file
"""

import collections
import hashlib
import re
import tempfile
from base64 import b64encode
from pathlib import Path

from .env import (
    DEFAULT_PYTHON_INTERPRETER,
    INIT_VENV_PACKAGES,
    BENTOBOX_VERSION,
    BOX_FILE_VERSION,
)
from .errors import (
    BoxNameError,
    BoxFileError,
)
from .package_repo import PackageRepo
from .util import (
    load_py_module,
)
from . import box_file


__all__ = [
    'check_box_name',
    'create_box_file',
]


Hash = hashlib.sha1


RE_BOX_NAME = re.compile(r"^\w+(?:\-\w+)*$")


def check_box_name(value):
    if not RE_BOX_NAME.match(value):
        raise BoxNameError(value)
    return value


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


        pkg_repo = PackageRepo(workdir=tmpdir)
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
    box_module = load_py_module(box_path)
    box_module.check(install_dir)  # pylint: disable=no-member
