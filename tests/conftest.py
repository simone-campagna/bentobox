from pathlib import Path

import pytest

THIS_DIR = Path(__file__).parent
EXAMPLES_DIR = THIS_DIR.parent / "examples"


@pytest.fixture
def examples_dir():
    return EXAMPLES_DIR
