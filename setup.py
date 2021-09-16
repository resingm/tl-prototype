#!/usr/bin/env python3
# coding: utf-8

"""
This script supports publishing tl to PyPI. The package will be published under
the name `timelog`. It will install an excutable `tl`.

Simply call `python setup.py sdist upload`
"""

import tl
import setuptools

FILE_ENCODING = "utf-8"
README_PATH = "README.md"
LICENSE_PATH = "LICENSE"

CLASSIFIERS = (
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: Unix',
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
)

INSTALL_REQUIRES = ['yacf', 'pretty-tables']
PACKAGES = ["tl"]
PYTHON_REQUIRES = '>=3.9'


def read(path):
    b = ""
    with open(path, 'rb') as f:
        b = f.read()

    return b.decode(FILE_ENCODING)


def build_descr():
    readme_md = read(README_PATH)
    license_md = "\n# LICENSE \n\n" + read(LICENSE_PATH)

    return "\n\n".join([readme_md, license_md])


def main():
    descr = build_descr()

    setuptools.setup(
        version='.'.join(map, tl.__version__),
        name='time_log',
        license='GPL-3.0',
        description='tl - Time logging/tracking utility for the command line',
        long_description=descr,
        author='Max Resing',
        author_email='max.resing@protonmail.com',
        maintainer='Max Resing',
        maintainer_email='max.resing@protonmail.com',
        url='https://github.com/resingm/tl-prototype',
        install_requires=INSTALL_REQUIRES,
        python_requres=PYTHON_REQUIRES,
        packages=PACKAGES,
        entry_points={
            'console_scripts': [
                'tl=time_log:main',
            ]
        },
        classifiers=CLASSIFIERS,
    )


if __name__ == "__main__":
    main()
