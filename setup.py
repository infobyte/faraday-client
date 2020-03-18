#!/usr/bin/env python

"""The setup script."""
from re import search

from setuptools import setup, find_packages

with open('faraday_client/__init__.py', 'rt', encoding='utf8') as f:
    version = search(r'__version__ = \'(.*?)\'', f.read()).group(1)


with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

with open('requirements.txt') as requirements:
    requirements = [requirement.strip('\n') for requirement in requirements.readlines()]

setup_requirements = []

test_requirements = []

setup(
    author="Matias Lang",
    author_email='matiasl@faradaysec.com',
    python_requires='>=3.5',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    description="Faraday GTK Client",
    install_requires=requirements,
    license="GNU General Public License v3",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='faraday_client',
    name='faraday_client',
    packages=find_packages(include=['faraday_client', 'faraday_client.*']),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/infobyte/faraday_client',
    version=version,
    zip_safe=False,
    entry_points={  # Optional
          'console_scripts': [
              'faraday-client=faraday_client.start_client:main',
              'fplugin=faraday_client.bin.fplugin:main',
          ],
      },
)
