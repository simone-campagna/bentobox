# -*- coding: utf-8 -*-
#
# Copyright 2020 Simone Campagna
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

__author__ = "Simone Campagna"

from setuptools import setup, find_packages


if __name__ == "__main__":
    setup(
        name="bentobox",
        version='0.0.1',
        requires=[],
        description="Self-installable python executables",
        author="Simone Campagna",
        author_email="simone.campagna11@gmail.com",
        install_requires=[],
        url='',
        download_url = '',
        package_dir={'': 'src'},
        packages=find_packages("src"),
        package_data={},
        entry_points={
            'console_scripts': [
                'bentobox=bentobox.cli:main',
            ],
        },
        classifiers=[
        ],
        keywords='self-installable python executable',
    )
