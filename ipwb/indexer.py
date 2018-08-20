#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
InterPlanetary Wayback indexer

This script reads a WARC file and returns a CDXJ representative of its
 contents. In doing so, it extracts all archived HTTP responses from
 warc-response records, separates the HTTP header from the body, pushes each
 into IPFS, and retains the hashes. These hashes are then used to populate the
 JSON block corresponding to the archived URI.
"""

from __future__ import print_function
import sys
import os
import json
import ipfsapi
import argparse
import zlib
import surt
import ntpath

from io import BytesIO
from pywb.warc.archiveiterator import DefaultRecordParser
# from pywb.utils.canonicalize import canonicalize as surt
from requests.packages.urllib3.exceptions import NewConnectionError
from pywb.warc.recordloader import ArchiveLoadFailed
from ipfsapi.exceptions import ConnectionError
# from requests.exceptions import ConnectionError

from six.moves import input

from .util import IPFSAPI_HOST, IPFSAPI_PORT

# from warcio.archiveiterator import ArchiveIterator

import requests
import datetime
import shutil

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import base64

from .__init__ import __version__ as ipwbVersion

DEBUG = False

IPFS_API = ipfsapi.Client(IPFSAPI_HOST, IPFSAPI_PORT)


# TODO: put this method definition below indexFileAt()
def pushToIPFS(hstr, payload):
    ipfsRetryCount = 5  # WARC->IPFS attempts before giving up
    retryCount = 0
    while retryCount < ipfsRetryCount:
        try:
            httpHeaderIPFSHash = pushBytesToIPFS(bytes(hstr, 'utf-8'))
            payloadIPFSHash = pushBytesToIPFS(bytes(payload))

            if retryCount > 0:
                m = 'Retrying succeeded after {0} attempts'.format(retryCount)
                print(m)

            return [httpHeaderIPFSHash, payloadIPFSHash]
        except NewConnectionError as e:
            print('IPFS daemon is likely not running.')
            print('Run "ipfs daemon" in another terminal session.')

            sys.exit()
        except Exception as e:  # TODO: Do not use bare except
            attemptCount = '{0}/{1}'.format(retryCount + 1, ipfsRetryCount)
            logError('IPFS failed to add, ' +
                     'retrying attempt {0}'.format(attemptCount))
            print(sys.exc_info())
            retryCount += 1

    return None  # Process of adding to IPFS failed


def encrypt(hstr, payload, encryptionKey):
    paddedEncryptionKey = pad(encryptionKey, AES.block_size)
    key = base64.b64encode(paddedEncryptionKey)
    cipher = AES.new(key, AES.MODE_CTR)

    hstrBytes = base64.b64encode(cipher.encrypt(hstr)).decode('utf-8')

    payloadBytes = base64.b64encode(cipher.encrypt(payload)).decode('utf-8')
    nonce = base64.b64encode(cipher.nonce).decode('utf-8')

    return [hstrBytes, payloadBytes, nonce]


def createIPFSTempPath():
    ipfsTempPath = '/tmp/ipfs/'

    # Create temp path for ipwb temp files if it does not already exist
    if not os.path.exists(ipfsTempPath):
        os.makedirs(ipfsTempPath)


def indexFileAt(warcPaths, encryptionKey=None,
                compressionLevel=None, encryptTHENCompress=True,
                quiet=False, outfile=None, debug=False):
    global DEBUG
    DEBUG = debug

    if type(warcPaths) is str:
        warcPaths = [warcPaths]

    for warcPath in warcPaths:
        verifyFileExists(warcPath)

    cdxjLines = []

    if outfile:
        outdir = os.path.dirname(os.path.abspath(outfile))
        if not os.path.exists(outdir):
            try:
                os.makedirs(outdir)
            except Exception as e:
                logError(e)
                logError('CDXJ output directory was not created')
        try:
            outputFile = open(outfile, 'a+')
            # Read existing non-meta lines (if any) to allow automatic merge
            cdxjLines = [l.strip() for l in outputFile if l[:1] != '!']
        except IOError as e:
            logError(e)
            logError('Writing generated CDXJ to STDOUT instead')
            outfile = None

    if encryptionKey is not None and len(encryptionKey) == 0:
        encryptionKey = askUserForEncryptionKey()
        if encryptionKey == '':
            encryptionKey = None
            logError('Blank key entered, encryption disabled')

    encryptionAndCompressionSetting = {
        'encryptTHENCompress': encryptTHENCompress,
        'encryptionKey': encryptionKey,
        'compressionLevel': compressionLevel
    }

    for warcPath in warcPaths:
        warcFileFullPath = warcPath

        try:
            cdxjLines += getCDXJLinesFromFile(
                warcFileFullPath, **encryptionAndCompressionSetting)
        except ArchiveLoadFailed:
            logError(warcPath + ' is not a valid WARC file.')

    # De-dupe and sort, needed for CDXJ adherence
    cdxjLines = list(set(cdxjLines))
    cdxjLines.sort()

    # Prepend metadata
    cdxjMetadataLines = generateCDXJMetadata(cdxjLines)
    cdxjLines = cdxjMetadataLines + cdxjLines

    if quiet:
        return cdxjLines

    if outfile:
        # Truncate existing CDXJ file contents (if any) before writing to it
        outputFile.seek(0)
        outputFile.truncate()
        for line in cdxjLines:
            outputFile.write(line + "\n")
        outputFile.close()
    else:
        print('\n'.join(cdxjLines))


def sanitizecdxjLine(cdxjLine):
    return cdxjLine


def getCDXJLinesFromFile(warcPath, **encCompOpts):
    textRecordParserOptions = {
        'cdxj': True,
        'include_all': False,
        'surt_ordered': False}
    iter = TextRecordParser(**textRecordParserOptions)

    recordCount = 0
    with open(warcPath, 'rb') as fhForCounting:
        iterForCounting = TextRecordParser(**textRecordParserOptions)
        recordCount = 0
        try:
            for i in iterForCounting(fhForCounting):
                recordCount += 1
                # recordCount = sum(1 for _ in iterForCounting(fhForCounting))
        except ArchiveLoadFailed:
            print('Encountered a bad WARC record.', file=sys.stderr)

    with open(warcPath, 'rb') as fh:
        cdxjLines = []
        recordsProcessed = 0
        # Throws pywb.warc.recordloader.ArchiveLoadFailed if not a warc
        for entry in iter(fh):
            msg = 'Processing WARC records in ' + ntpath.basename(warcPath)
            showProgress(msg, recordsProcessed, recordCount)

            recordsProcessed += 1
            # Only consider WARC resps records from reqs for web resources
            ''' TODO: Change conditional to return on non-HTTP responses
                      to reduce branch depth'''
            if entry.record.rec_type != 'response' or \
               entry.get('mime') in ('text/dns', 'text/whois'):
                continue

            hdrs = entry.record.status_headers
            hstr = hdrs.protocol + ' ' + hdrs.statusline
            for h in hdrs.headers:
                hstr += "\n" + ': '.join(h)
            try:
                statusCode = hdrs.statusline.split()[0]
            except Exception as e:  # TODO: Do not use bare except
                break

            if not entry.buffer:
                return

            entry.buffer.seek(0)
            payload = entry.buffer.read()

            httpHeaderIPFSHash = ''
            payloadIPFSHash = ''
            retryCount = 0
            nonce = ''

            if encCompOpts.get('encryptTHENCompress'):
                if encCompOpts.get('encryptionKey') is not None:
                    key = encCompOpts.get('encryptionKey')
                    (hstr, payload, nonce) = encrypt(hstr, payload, key)
                if encCompOpts.get('compressionLevel') is not None:
                    compressionLevel = encCompOpts.get('compressionLevel')
                    hstr = zlib.compress(hstr, compressionLevel)
                    payload = zlib.compress(payload, compressionLevel)
            else:
                if encCompOpts.get('compressionLevel') is not None:
                    compressionLevel = encCompOpts.get('compressionLevel')
                    hstr = zlib.compress(hstr, compressionLevel)
                    payload = zlib.compress(payload, compressionLevel)
                if encCompOpts.get('encryptionKey') is not None:
                    encryptionKey = encCompOpts.get('encryptionKey')
                    (hstr, payload, nonce) = \
                        encrypt(hstr, payload, encryptionKey)

            # print('Adding {0} to IPFS'.format(entry.get('url')))
            ipfsHashes = pushToIPFS(hstr, payload)

            if ipfsHashes is None:
                logError('Skipping ' + entry.get('url'))

                continue

            (httpHeaderIPFSHash, payloadIPFSHash) = ipfsHashes

            originaluri = entry.get('url')
            originaluri_surted = \
                surt.surt(originaluri,
                          path_strip_trailing_slash_unless_empty=False)
            timestamp = entry.get('timestamp')
            mime = entry.get('mime')
            obj = {
                'locator': 'urn:ipfs/{0}/{1}'.format(
                    httpHeaderIPFSHash, payloadIPFSHash),
                'status_code': statusCode,
                'mime_type': mime,
                'original_uri': originaluri
            }
            if encCompOpts.get('encryptionKey') is not None:
                obj['encryption_key'] = encCompOpts.get('encryptionKey')
                obj['encryption_method'] = 'aes'
                obj['encryption_nonce'] = nonce

            objJSON = json.dumps(obj)

            cdxjLine = '{0} {1} {2}'.format(originaluri_surted,
                                            timestamp, objJSON)
            cdxjLines.append(cdxjLine)  # + '\n'
        return cdxjLines


def generateCDXJMetadata(cdxjLines=None):
    metadata = ['!context ["http://tools.ietf.org/html/rfc7089"]']
    metaVals = {
        'generator': "InterPlanetary Wayback v.{0}".format(ipwbVersion),
        'created_at': '{0}'.format(datetime.datetime.now().isoformat())
    }
    metaVals = '!meta {0}'.format(json.dumps(metaVals))
    metadata.append(metaVals)

    return metadata


def askUserForEncryptionKey():
    if DEBUG:  # Allows testing instead of requiring a user prompt
        return 'ipwb'

    outputRedirected = os.fstat(0) != os.fstat(1)
    promptString = 'Enter a key for encryption: '
    if outputRedirected:  # Prevents prompt in redir output
        logError(promptString, end='')
        promptString = ''

    key = input(promptString)

    return key


def verifyDaemonIsAlive(hostAndPort):
    """Ensure that the IPFS daemon is running via HTTP before proceeding"""
    try:
        requests.get('http://' + hostAndPort)
    except ConnectionError:
        print('Daemon is not running at http://' + hostAndPort)
        sys.exit()


def verifyFileExists(warcPath):
    if os.path.isfile(warcPath):
        return
    logError('File at ' + warcPath + ' does not exist!')
    sys.exit()


def showProgress(msg, i, n):
    line = '{0}: {1}/{2}'.format(msg, i, n)
    print(line, file=sys.stderr, end='\r')
    # Clear status line, show complete msg
    if i == n - 1:
        finalMsg = msg + ' complete'
        spaceDelta = len(finalMsg) - len(msg)
        spaces = '' * spaceDelta if spaceDelta > 0 else ''
        print(finalMsg + spaces, file=sys.stderr, end='\r\n')


def logError(errIn, end='\n'):
    print(errIn, file=sys.stderr, end=end)


def pullFromIPFS(hash):
    global IPFS_API
    return IPFS_API.cat(hash)


def pushBytesToIPFS(bytes):
    """
    Call the IPFS API to add the byte string to IPFS.
    When IPFS returns a hash, return this to the caller
    """
    global IPFS_API
    res = IPFS_API.add_bytes(bytes)  # bytes)
    # TODO: verify that the add was successful

    # Receiving weirdness where res is sometimes a dictionary and sometimes
    #  a unicode string

    if isinstance(type(res).__name__, str):
        return res

    return res[0]['Hash']


def writeFile(filename, content):
    with open(filename, 'w') as tmpFile:
        tmpFile.write(content)


class TextRecordParser(DefaultRecordParser):
    def create_payload_buffer(self, entry):
        return BytesIO()

    def create_record_iter(self, raw_iter):
        raw_iter.INC_RECORD = ''
        return super(TextRecordParser, self).create_record_iter(raw_iter)
