import functools
import tempfile

from pathlib import Path

from importlib.util import spec_from_file_location, module_from_spec

__all__ = [
    'load_py_module',
]


def load_py_module(module_path):
    module_path = Path(module_path).resolve()
    return _load_py_module(module_path)


@functools.lru_cache(maxsize=10)
def _load_py_module(module_path):
    with tempfile.TemporaryDirectory() as tmpd:
        module_name = module_path.name
        module_link = Path(tmpd) / (module_name + ".py")
        module_link.symlink_to(module_path)
        spec = spec_from_file_location(module_name, str(module_link))
        module = module_from_spec(spec)
        module.__file__ = str(module_path)
        spec.loader.exec_module(module)
        return module
