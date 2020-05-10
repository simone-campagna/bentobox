import tempfile
from pathlib import Path

import pytest

from bentobox.util import load_py_module


def test_load_py_module():
    with tempfile.TemporaryDirectory() as tmpd:
        mod_path = Path(tmpd) / "mymod"
        with open(mod_path, "w") as fmod:
            fmod.write("""\
def foo(i, j):
    return i * j
""")
        mod = load_py_module(mod_path)
        assert mod.__name__ == "mymod"
        assert mod.foo(2, 4) == 8
