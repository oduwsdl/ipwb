# Number of entries in CDXJ == number of response records in WARC

import pytest
from . import testUtil as ipwb_test
import os

from ipwb import indexer

from pathlib import Path


def test_cdxj_warc_responserecord_count():
    new_warc_path = ipwb_test.createUniqueWARC()
    # use ipwb indexer to push
    cdxjList = indexer.index_file_at(new_warc_path, quiet=True)
    cdxj = '\n'.join(cdxjList)
    assert ipwb_test.count_cdxj_entries(cdxj) == 2


# A response record's content-length causes the payload to truncate
# WARC-Response record for html should still exist in output
def test_warc_ipwb_indexer_broken_warc_record():
    pathOfBrokenWARC = os.path.join(
        Path(os.path.dirname(__file__)).parent,
        'samples', 'warcs', 'broken.warc')
    cdxjList = indexer.index_file_at(pathOfBrokenWARC, quiet=True)
    cdxj = '\n'.join(cdxjList)
    assert ipwb_test.count_cdxj_entries(cdxj) == 1


# WARC/1.1 allows for dates of length that are not easily converted
# to 14-digits. This test highlights the failures from a WARC
# exhibiting these dates.
@pytest.mark.ipwbIndexerVariableSizedDates
def test_warc_ipwbIndexerVariableSizedDates():
    pathOfBrokenWARC = \
        os.path.normpath(os.path.join(os.path.dirname(__file__), '..',
                         'samples', 'warcs', 'variableSizedDates.warc'))
    indexer.indexFileAt(pathOfBrokenWARC, quiet=True)

# TODO: Have unit tests for each function in indexer.py
