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
        name="simple-calc",
        version='0.0.1',
        requires=[],
        description="Pybot simple test project (one library, no dependencies)",
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
                'simple-add=simple_calc.cli:main_add',
                'simple-mul=simple_calc.cli:main_mul',
                'simple-sub=simple_calc.cli:main_sub',
                'simple-div=simple_calc.cli:main_div',
                'simple-pow=simple_calc.cli:main_pow',
                'simple-calc=simple_calc.cli:main_calc',
            ],
        },
    )
