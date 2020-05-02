import functools
import tempfile

from pathlib import Path

from importlib.util import spec_from_file_location, module_from_spec

__all__ = [
    'load_box_module',
]


def load_box_module(box_path):
    box_path = Path(box_path).resolve()
    return _load_box_module(box_path)


@functools.lru_cache(maxsize=10)
def _load_box_module(box_path):
    with tempfile.TemporaryDirectory() as tmpd:
        box_name = box_path.name
        box_link = Path(tmpd) / (box_name + ".py")
        box_link.symlink_to(box_path)
        spec = spec_from_file_location(box_name, str(box_link))
        module = module_from_spec(spec)
        module.__file__ = str(box_path)
        spec.loader.exec_module(module)
        return module
