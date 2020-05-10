import tempfile
from pathlib import Path

import pytest

from bentobox.env import get_bentobox_version


def test_get_bentobox_version():
    assert get_bentobox_version() == "0.1.0"
