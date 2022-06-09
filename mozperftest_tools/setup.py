import sys

import setuptools

PACKAGE_NAME = "mozperftest_tools"
PACKAGE_VERSION = "0.1.1"

# dependencies
deps = ["matplotlib", "opencv-python", "requests"]
if sys.version_info <= (3, 7):
    # With versions <=3.7, we need to explicitly set
    # the max version or else pip will try to get the
    # latest version that only work with 3.8+
    deps.extend([
        "numpy<1.21",
        "scipy<1.8",
    ])
else:
    deps.extend([
        "numpy",
        "scipy",
    ])


with open("README.md", "r", encoding="utf-8") as fh:
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
    python_requires=">=3.6, <3.10",
)
