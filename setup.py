#!/usr/bin/env python
# encoding: utf-8

from setuptools import setup, find_packages

setup(
    name='sortphotos',
    version='1.0',
    description='Organizes photos and videos into folders using date/time information ',
    author='Andrew Ning',
    packages=find_packages(),
    include_package_data=True,
    license='MIT License',
    install_requires=[
        # List of modules which are imported by the project.
        # But not core modules like subprocess or os.
        'argparse',
        'logging',
        'dill',
        'scrollviews==0.2.1'
    ],
    dependency_links=[
        "git+https://github.com/thuel/scrollviews.py.git@0.2.1#egg=scrollviews-0.2.1"
    ],
    entry_points={
        'console_scripts': [
          'sortphotos = sortphotos.sortphotos:main',
          'dirmon = sortphotos.dirmon:main',
          'upmondirs = sortphotos.upmondirs:main',
          'exifqry = sortphotos.exifqry:main'
        ]
      }
)

