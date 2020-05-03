"""
Environment
"""

import os
from pathlib import Path

__all__ = [
    'DEFAULT_PYTHON_INTERPRETER',
    'get_bentobox_version',
    'get_bentobox_home',
    'get_bentobox_boxes_dir',
]


DEFAULT_PYTHON_INTERPRETER = '/usr/bin/env python3'

BENTOBOX_VERSION = '0.1.0'

def get_bentobox_version():
    return BENTOBOX_VERSION

BENTOBOX_HOME = os.environ.get("BENTOBOX_HOME", None)
if BENTOBOX_HOME is None:
    BENTOBOX_HOME = Path.home().joinpath(".bentobox")
else:
    BENTOBOX_HOME = Path(BENTOBOX_HOME).resolve()


def get_bentobox_home():
    return BENTOBOX_HOME


def get_bentobox_boxes_dir():
    return BENTOBOX_HOME.joinpath("boxes")
