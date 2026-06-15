import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_setup_module():
    spec = importlib.util.spec_from_file_location('setup_module', ROOT / 'setup.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_setup_uses_pipfile_runtime_dependencies():
    setup_module = _load_setup_module()

    assert setup_module.get_setup_kwargs()['install_requires'] == [
        'warcio>=1.5.3',
        'ipfshttpclient>=0.8.0a',
        'Flask>=3.0',
        'pycryptodome>=3.4.11',
        'requests>=2.19.1',
        'beautifulsoup4>=4.6.3',
        'surt>=0.3.0',
        'multiaddr>=0.0.9',
        'packaging==23.0'
    ]


def test_setup_uses_pipfile_dev_dependencies():
    setup_module = _load_setup_module()

    assert setup_module.get_setup_kwargs()['tests_require'] == [
        'flake8>=3.7.9',
        'pycodestyle',
        'pytest>=5.3.5,<9',
        'pytest-cov',
        'pytest-flake8'
    ]
