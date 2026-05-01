from unittest.mock import MagicMock, patch

import pytest

from ipwb.util import check_daemon_is_alive, create_ipfs_client
from ipfshttpclient.exceptions import ConnectionError


def test_exception():
    mock_client = MagicMock()
    mock_client.side_effect = Exception('boo!')
    expected_error = 'Cannot create an IPFS client.'

    with patch('ipfshttpclient.Client', mock_client):
        with pytest.raises(Exception, match=expected_error):
            create_ipfs_client()


def test_is_alive():
    mock_client = MagicMock()

    with patch('ipwb.util.ipfs_client', mock_client):
        assert check_daemon_is_alive() is True


def test_connection_error():
    mock_client = MagicMock()
    mock_client.return_value.id.side_effect = ConnectionError('boo!')

    with patch('ipwb.util.ipfs_client', mock_client):
        with pytest.raises(Exception, match='Daemon is not running at'):
            check_daemon_is_alive()


def test_os_error():
    mock_client = MagicMock()
    mock_client.return_value.id.side_effect = OSError('foo!')

    with patch('ipwb.util.ipfs_client', mock_client):
        with pytest.raises(Exception, match='IPFS is likely not installed'):
            check_daemon_is_alive()


def test_unknown_error():
    mock_client = MagicMock()
    mock_client.return_value.id.side_effect = Exception('foo!')
    expected_error = 'Unknown error in retrieving IPFS daemon status.'

    with patch('ipwb.util.ipfs_client', mock_client):
        with pytest.raises(Exception, match=expected_error):
            check_daemon_is_alive()
