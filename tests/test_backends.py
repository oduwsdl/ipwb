from unittest import mock

import pytest
from ipfshttpclient.exceptions import StatusError

from ipwb.backends import get_web_archive_index, BackendError
from pathlib import Path


SAMPLE_INDEX = str(
    Path(__file__).parent.parent / 'samples/indexes/salam-home.cdxj'
)


def test_local():
    assert get_web_archive_index(SAMPLE_INDEX).startswith(
        '!context ["https://tools.ietf.org/html/rfc7089"]'
    )


def test_https():
    assert get_web_archive_index(
        'https://raw.githubusercontent.com/oduwsdl/ipwb/master/samples/' +
        'indexes/salam-home.cdxj'
    ).startswith('!context ["https://tools.ietf.org/html/rfc7089"]')


def test_ipfs_success():
    with open(SAMPLE_INDEX, 'r') as f:
        expected_content = f.read()

    connect_to_ipfs = mock.MagicMock()
    connect_to_ipfs.return_value.cat.return_value = expected_content

    with mock.patch('ipfshttpclient.connect', connect_to_ipfs):
        assert get_web_archive_index(
            'QmReQCtRpmEhdWZVLhoE3e8bqreD8G3avGpVfcLD7r4K6W'
        ).startswith('!context ["https://tools.ietf.org/html/rfc7089"]')


def test_ipfs_failure():
    with pytest.raises(BackendError) as err_info:
        with mock.patch(
            'ipfshttpclient.client.Client.cat',
            side_effect=StatusError(original='')
        ):
            get_web_archive_index(
                'QmReQCtRpmEhdWZVLhoE3e8bqreD8G3avGpVfcLD7r4K6W',
            )

    assert str(err_info.value) == (
        'Cannot load index file from ipfs.'
    )


def test_ipfs_url_success():
    with open(SAMPLE_INDEX, 'r') as f:
        expected_content = f.read()

    connect_to_ipfs = mock.MagicMock()
    connect_to_ipfs.return_value.cat.return_value = expected_content

    with mock.patch('ipfshttpclient.connect', connect_to_ipfs):
        assert get_web_archive_index(
            'ipfs://QmReQCtRpmEhdWZVLhoE3e8bqreD8G3avGpVfcLD7r4K6W'
        ).startswith('!context ["https://tools.ietf.org/html/rfc7089"]')
