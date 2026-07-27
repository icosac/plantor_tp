import os

from setuptools import find_packages, setup

with open("version.txt", "r") as file_handler:
    __version__ = file_handler.read().strip()


setup(
    name="PLANTOR",
    packages=[package for package in find_packages()],
    package_data={},
    install_requires=[],
    extras_require={},
    description="PLANTOR",
    author="Enrico Saccon",
    url="",
    author_email="enrico.saccon@unitn.it",
    keywords="",
    license="Apache-2.0",
    long_description="",
    long_description_content_type="text/markdown",
    version=__version__,
    python_requires=">=3.9",
    # PyPI package information.
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",        
    ],
)