"""
Environment
"""

__all__ = [
    'DEFAULT_PYPI_INDEX_URL',
    'DEFAULT_PYTHON_INTERPRETER',
    'INIT_VENV_PACKAGES',
    'get_bentobox_version',
]


DEFAULT_PYPI_INDEX_URL = 'https://pypi.org/simple'
DEFAULT_PYTHON_INTERPRETER = '/usr/bin/env python3'
INIT_VENV_PACKAGES = ('setuptools', 'pip')

BENTOBOX_VERSION = '0.1.0'
BOX_FILE_VERSION = 1

def get_bentobox_version():
    return BENTOBOX_VERSION
