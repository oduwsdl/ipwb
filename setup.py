#!/usr/bin/env python

from pathlib import Path

from setuptools import setup

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent
PACKAGE_INIT = ROOT / 'ipwb' / '__init__.py'
PIPFILE = ROOT / 'Pipfile'
README = ROOT / 'README.md'
desc = """InterPlanetary Wayback (ipwb): Web Archive integration with IPFS"""


def _load_version():
    for line in PACKAGE_INIT.read_text().splitlines():
        if line.startswith('__version__ = '):
            return line.split('=', 1)[1].strip().strip("'\"")
    raise RuntimeError('Unable to determine package version.')


def _load_requirements(group):
    with PIPFILE.open('rb') as fh:
        dependencies = tomllib.load(fh)

    return [
        package if specifier == '*' else f'{package}{specifier}'
        for package, specifier in dependencies[group].items()
    ]


def get_setup_kwargs():
    return {
        'name': 'ipwb',
        'version': _load_version(),
        'url': 'https://github.com/oduwsdl/ipwb',
        'download_url': "https://github.com/oduwsdl/ipwb",
        'author': 'Mat Kelly',
        'author_email': 'me@matkelly.com',
        'description': desc,
        'packages': ['ipwb'],
        'python_requires': '>=3.9',
        'license': 'MIT',
        'long_description': README.read_text(),
        'long_description_content_type': "text/markdown",
        'provides': [
            'ipwb'
        ],
        'install_requires': _load_requirements('packages'),
        'tests_require': _load_requirements('dev-packages'),
        'extras_require': {
            'test': _load_requirements('dev-packages')
        },
        'entry_points': """
            [console_scripts]
            ipwb = ipwb.__main__:main
        """,
        'package_data': {
            'ipwb': [
                'assets/*.*',
                'assets/favicons/*.*',
                'templates/*.*'
              ]
        },
        'zip_safe': False,
        'keywords': 'http web archives ipfs distributed odu wayback memento',
        'classifiers': [
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
    }


if __name__ == '__main__':
    setup(**get_setup_kwargs())

# Publish to pypi:
#   rm -rf dist; python setup.py sdist bdist_wheel; twine upload dist/*
