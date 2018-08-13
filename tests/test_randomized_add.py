import pytest
import os
import sys
import json

from ipwb import indexer

from . import testUtil as ipwbTest


def isValidSURT(surt):
    return True  # The surt library does not yet have a way to check this


def isValidDatetime(dt):
    return len(dt) == 14 and dt.isdigit()


def isValidJSON(jsonIn):
    try:
        j = json.loads(json.dumps(jsonIn))
    except ValueError:
        return False
    return True


def checkCDXJFields(cdxjEntry):
    (surt, dt, json) = cdxjEntry.split(' ', 2)
    validSURT = isValidSURT(surt)
    validDT = isValidDatetime(dt)
    validJSON = isValidJSON(json)

    return validSURT and validDT and validJSON


def checkIPWBJSONFieldPresesence(jsonStr):
    keys = json.loads(jsonStr)
    return 'locator' in keys and 'mime_type' in keys and 'status_code' in keys


@pytest.mark.ipfsDaemonInteraction
def test_push():
    """
    Read WARC, manipulate content to ensure uniqueness, push to IPFS
      WARC should result in two CDXJ entries with three space-limited fields
      each: surt URI, datetime, JSON
      JSON should contain AT LEAST locator, mime_type, and status fields
    """
    newWARCPath = ipwbTest.createUniqueWARC()
    # use ipwb indexer to push
    cdxjList = indexer.indexFileAt(newWARCPath, quiet=True)
    cdxj = '\n'.join(cdxjList)

    firstEntry = cdxj.split('\n')[0]
    firstNonMetadataEntry = ''
    for line in cdxj.split('\n'):
        if line[0] != '!':
            firstNonMetadataEntry = line
            break

    assert checkCDXJFields(firstNonMetadataEntry)
    firstEntryLastField = firstNonMetadataEntry.split(' ', 2)[2]
    assert checkIPWBJSONFieldPresesence(firstEntryLastField)
