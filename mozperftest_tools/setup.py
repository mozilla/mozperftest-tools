# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import pathlib
import sys
import setuptools

PACKAGE_NAME = "mozperftest_tools"
PACKAGE_VERSION = "0.2.7"
HERE = pathlib.Path(__file__).parent.resolve()

# dependencies
deps = ["requests"]
python_version = (sys.version_info.major, sys.version_info.minor)
if python_version <= (3, 7):
    # With versions <=3.7, we need to explicitly set
    # the max version or else pip will try to get the
    # latest version that only work with 3.8+
    deps.extend([
        "opencv-python==4.5.4.60",
        "numpy<1.21",
        "scipy<1.8",
    ])
elif python_version == (3, 8):
    deps.extend([
        "opencv-python==4.5.4.60",
        "numpy==1.22.0",
        "scipy==1.7.3",
    ])
else:
    deps.extend([
        "opencv-python",
        "numpy",
        "scipy",
    ])


with pathlib.Path(HERE, "README.md").open(encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name=PACKAGE_NAME,
    version=PACKAGE_VERSION,
    description=("This repository is a collection of various tools that are useful for"
                 "the things we do in Performance and Performance Testing. "),
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
    python_requires=">=3.6, <3.11",
    license_files = (str(pathlib.Path(HERE, "..", "LICENSE.md").resolve()),),
)
