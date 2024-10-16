import pytest
from unittest.mock import MagicMock, patch, ANY

from ipwb.error_handler import exception_logger


@exception_logger(catch=False)
def reraised_error(arg):
    raise Exception(arg)


@exception_logger()
def caught_error(arg):
    raise Exception(arg)


def test_re_raise():
    with pytest.raises(Exception, match='foo'):
        reraised_error('foo')


def test_catch():
    mock_logger = MagicMock()
    with patch('ipwb.error_handler.logger.critical', mock_logger):
        caught_error('boo')

    mock_logger.assert_called_once_with('boo')
