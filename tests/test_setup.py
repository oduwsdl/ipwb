import importlib.util
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]


def _load_setup_module():
    spec = importlib.util.spec_from_file_location('setup_module', ROOT / 'setup.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_setup_uses_pipfile_runtime_dependencies():
    setup_module = _load_setup_module()
    with (ROOT / 'Pipfile').open('rb') as fh:
        pipfile = tomllib.load(fh)

    assert setup_module.get_setup_kwargs()['install_requires'] == [
        package if specifier == '*' else f'{package}{specifier}'
        for package, specifier in pipfile['packages'].items()
    ]


def test_setup_uses_pipfile_dev_dependencies():
    setup_module = _load_setup_module()
    with (ROOT / 'Pipfile').open('rb') as fh:
        pipfile = tomllib.load(fh)

    assert setup_module.get_setup_kwargs()['tests_require'] == [
        package if specifier == '*' else f'{package}{specifier}'
        for package, specifier in pipfile['dev-packages'].items()
    ]
