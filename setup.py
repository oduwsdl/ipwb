#!/usr/bin/env python

from setuptools import setup
from ipwb import __version__

with open('README.md') as f:
    long_description = f.read()
desc = """InterPlanetary Wayback (ipwb): Web Archive integration with IPFS"""

setup(
    name='ipwb',
    version=__version__,
    url='https://github.com/oduwsdl/ipwb',
    download_url="https://github.com/oduwsdl/ipwb",
    author='Mat Kelly',
    author_email='me@matkelly.com',
    description=desc,
    packages=['ipwb'],
    python_requires='>=3.9',
    license='MIT',
    long_description=long_description,
    long_description_content_type="text/markdown",
    provides=[
        'ipwb'
    ],
    install_requires=[
        'warcio>=1.5.3',
        'ipfshttpclient>=0.8.0a',
        'Flask>=3.0',
        'pycryptodome>=3.4.11',
        'requests>=2.19.1',
        'beautifulsoup4>=4.6.3',
        'surt>=0.3.0'
    ],
    tests_require=[
        'flake8>=3.4',
        'pytest>=3.6',
        'pytest-cov',
        'pytest-flake8'
    ],
    entry_points="""
        [console_scripts]
        ipwb = ipwb.__main__:main
    """,
    package_data={
        'ipwb': [
            'assets/*.*',
            'assets/favicons/*.*',
            'templates/*.*'
          ]
    },
    zip_safe=False,
    keywords='http web archives ipfs distributed odu wayback memento',
    classifiers=[
        'Development Status :: 4 - Beta',

        'Environment :: Web Environment',

        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',

        'License :: OSI Approved :: MIT License',

        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Science/Research',

        'Topic :: Internet :: WWW/HTTP',
        'Topic :: System :: Archiving',
        'Topic :: System :: Archiving :: Backup',
        'Topic :: System :: Archiving :: Mirroring',
        'Topic :: Utilities',
    ]
)

# Publish to pypi:
#   rm -rf dist; python setup.py sdist bdist_wheel; twine upload dist/*
