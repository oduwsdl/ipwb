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
    author_email='mkelly@cs.odu.edu',
    description=desc,
    packages=['ipwb'],
    license='MIT',
    long_description=long_description,
    long_description_content_type="text/markdown",
    provides=[
        'ipwb'
    ],
    install_requires=[
        'pywb==0.33.2',
        'ipfsapi>=0.4.2',
        'Flask==0.12.2',
        'pycryptodome>=3.4.11',
        'requests>=2.19.1',
        'six'
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
            'serviceWorker.js',
            'reconstructive.js',
            'reconstructive-banner.js',
            'webui/*.*',
            'webui/favicons/*.*',
            'samples/indexes/*.*',
            'samples/warcs/*.*'
          ]
    },
    keywords='http web archives ipfs distributed odu wayback memento',
    classifiers=[
        'Development Status :: 3 - Alpha',

        'Environment :: Web Environment',

        'Programming Language :: Python :: 2.7',

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
