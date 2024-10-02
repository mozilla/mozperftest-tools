# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import pathlib
import sys
import setuptools

PACKAGE_NAME = "mozperftest_tools"
PACKAGE_VERSION = "0.4.3"
HERE = pathlib.Path(__file__).parent.resolve()

# dependencies
deps = [
    "requests",
    "opencv-python==4.5.4.60; python_version<='3.7'",
    "numpy<1.21; python_version<='3.7'",
    "scipy<1.8; python_version<='3.7'",
    "opencv-python==4.8.1.78; python_version>='3.8'",
    "numpy>=1.23.5; python_version>='3.8'",
    "scipy==1.10.0; python_version>='3.8'",
]


with pathlib.Path(HERE, "README.md").open(encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name=PACKAGE_NAME,
    version=PACKAGE_VERSION,
    description=(
        "This repository is a collection of various tools that are useful for"
        "the things we do in Performance and Performance Testing. "
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mozilla/mozperftest-tools",
    project_urls={
        "Bug Tracker": "https://github.com/mozilla/mozperftest-tools/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
    keywords="mozilla",
    author="Firefox Performance Test Engineering team",
    author_email="perftest@mozilla.com",
    package_dir={"mozperftest_tools": "mozperftest_tools"},
    install_requires=deps,
    packages=setuptools.find_packages(where="."),
    python_requires=">=3.6",
    license_files=(str(pathlib.Path(HERE, "..", "LICENSE.md").resolve()),),
)
