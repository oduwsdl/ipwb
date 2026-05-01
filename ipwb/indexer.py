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

import sys
import os
import json
import ipfshttpclient as ipfsapi
import zlib
import surt
import ntpath
import traceback
import tempfile

from io import BytesIO
from warcio.archiveiterator import ArchiveIterator
from warcio.recordloader import ArchiveLoadFailed

from requests.packages.urllib3.exceptions import NewConnectionError
from ipfshttpclient.exceptions import ConnectionError
# from requests.exceptions import ConnectionError

from ipwb.util import iso8601_to_digits14, ipfs_client

import requests
import datetime

from bs4 import BeautifulSoup

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import base64

from .__init__ import __version__ as ipwb_version

DEBUG = False


def s2b(s):  # Convert str to bytes, cross-py
    return bytes(s, 'utf-8')


# TODO: put this method definition below index_file_at()
def push_to_ipfs(hstr, payload):
    ipfs_retry_count = 5  # WARC->IPFS attempts before giving up
    retry_count = 0
    while retry_count < ipfs_retry_count:
        try:
            # Py 2/3 str/unicode/byte resolution
            if isinstance(hstr, str):
                hstr = s2b(hstr)
            if isinstance(payload, str):
                payload = s2b(payload)

            if len(payload) == 0:  # py-ipfs-api issue #137
                return

            http_header_ipfs_hash = push_bytes_to_ipfs(hstr)
            payload_ipfs_hash = push_bytes_to_ipfs(payload)

            if retry_count > 0:
                m = f'Retrying succeeded after {retry_count} attempts'
                print(m)
            return [http_header_ipfs_hash, payload_ipfs_hash]
        except NewConnectionError as _:
            print('IPFS daemon is likely not running.')
            print('Run "ipfs daemon" in another terminal session.')

            sys.exit()
        except Exception as _:  # TODO: Do not use bare except
            attempt_count = f'{retry_count + 1}/{ipfs_retry_count}'
            log_error(f'IPFS failed to add, retrying attempt {attempt_count}')
            log_error(sys.exc_info())
            traceback.print_tb(sys.exc_info()[-1])

            retry_count += 1

    return None  # Process of adding to IPFS failed


def encrypt(hstr, payload, encryption_key):
    padded_encryption_key = pad(encryption_key, AES.block_size)
    key = base64.b64encode(padded_encryption_key)
    cipher = AES.new(key, AES.MODE_CTR)

    hstr_bytes = base64.b64encode(cipher.encrypt(hstr)).decode('utf-8')

    payload_bytes = base64.b64encode(cipher.encrypt(payload)).decode('utf-8')
    nonce = base64.b64encode(cipher.nonce).decode('utf-8')

    return [hstr_bytes, payload_bytes, nonce]


def create_ipfs_temp_path():
    ipfs_temp_path = tempfile.gettempdir() + '/ipfs/'

    # Create temp path for ipwb temp files if it does not already exist
    if not os.path.exists(ipfs_temp_path):
        os.makedirs(ipfs_temp_path)


def index_file_at(warc_paths, encryption_key=None,
                  compression_level=None, encrypt_then_compress=True,
                  quiet=False, outfile=None, debug=False):
    global DEBUG
    DEBUG = debug

    if type(warc_paths) is str:
        warc_paths = [warc_paths]

    for warc_path in warc_paths:
        verify_file_exists(warc_path)

    cdxj_lines = []

    if outfile:
        outdir = os.path.dirname(os.path.abspath(outfile))
        if not os.path.exists(outdir):
            try:
                os.makedirs(outdir)
            except Exception as e:
                log_error(e)
                log_error('CDXJ output directory was not created')
        try:
            output_file = open(outfile, 'a+')
            # Read existing non-meta lines (if any) to allow automatic merge
            cdxj_lines = [ln.strip() for ln in output_file if ln[:1] != '!']
        except IOError as e:
            log_error(e)
            log_error('Writing generated CDXJ to STDOUT instead')
            outfile = None

    if encryption_key is not None and len(encryption_key) == 0:
        encryption_key = ask_user_for_encryption_key()
        if encryption_key == '':
            encryption_key = None
            log_error('Blank key entered, encryption disabled')

    encryption_and_compression_setting = {
        'encrypt_THEN_compress': encrypt_then_compress,
        'encryption_key': encryption_key,
        'compression_level': compression_level
    }

    for warc_path in warc_paths:
        warc_file_full_path = warc_path

        try:
            cdxj_lines += cdx_cdxj_lines_from_file(
                warc_file_full_path, **encryption_and_compression_setting)
        except ArchiveLoadFailed:
            log_error(warc_path + ' is not a valid WARC file.')

    # De-dupe and sort, needed for CDXJ adherence
    cdxj_lines = list(set(cdxj_lines))
    cdxj_lines.sort()

    # Prepend metadata
    cdxj_metadata_lines = generate_cdxj_metadata(cdxj_lines)
    cdxj_lines = cdxj_metadata_lines + cdxj_lines

    if quiet:
        return cdxj_lines

    if outfile:
        # Truncate existing CDXJ file contents (if any) before writing to it
        output_file.seek(0)
        output_file.truncate()
        for line in cdxj_lines:
            output_file.write(line + "\n")
        output_file.close()
    else:
        print('\n'.join(cdxj_lines))


def sanitize_cdxj_line(cdxj_line):
    return cdxj_line


def cdx_cdxj_lines_from_file(warc_path, **enc_comp_opts):
    record_count = 0
    with open(warc_path, 'rb') as fhForCounting:
        record_count = 0
        try:
            for _ in ArchiveIterator(fhForCounting):
                record_count += 1

        except ArchiveLoadFailed:
            print('Encountered a bad WARC record.', file=sys.stderr)

    with open(warc_path, 'rb') as fh:
        cdxj_lines = []
        records_processed = 0
        # Throws pywb.warc.recordloader.ArchiveLoadFailed if not a warc
        for record in ArchiveIterator(fh):
            msg = f'Processing WARC records in {ntpath.basename(warc_path)}'
            show_progress(msg, records_processed, record_count)

            records_processed += 1
            # Only consider WARC resps records from reqs for web resources
            ''' TODO: Change conditional to return on non-HTTP responses
                      to reduce branch depth'''
            if record.rec_type != 'response' or \
               record.rec_headers.get_header('Content-Type') in \
                    ('text/dns', 'text/whois'):
                continue

            hstr = record.http_headers.to_str().strip()

            try:
                status_code = record.http_headers.statusline.split()[0]
            except Exception as _:  # TODO: Do not use bare except
                break

            payload = record.content_stream().read()

            title = None
            try:
                ctype = record.http_headers.get_header('content-type')
                if ctype and ctype.lower().startswith('text/html'):
                    title = BeautifulSoup(payload, 'html.parser').title
                    if title is not None:
                        title = ' '.join(title.text.split()) or None
            except Exception as e:
                print('Failed to extract title', file=sys.stderr)
                print(e, file=sys.stderr)

            http_header_ipfs_hash = ''
            payload_ipfs_hash = ''
            retry_count = 0
            nonce = ''

            if enc_comp_opts.get('encrypt_THEN_compress'):
                if enc_comp_opts.get('encryption_key') is not None:
                    key = enc_comp_opts.get('encryption_key')
                    (hstr, payload, nonce) = encrypt(hstr, payload, key)
                if enc_comp_opts.get('compression_level') is not None:
                    compression_level = enc_comp_opts.get('compression_level')
                    hstr = zlib.compress(hstr, compression_level)
                    payload = zlib.compress(payload, compression_level)
            else:
                if enc_comp_opts.get('compression_level') is not None:
                    compression_level = enc_comp_opts.get('compression_level')
                    hstr = zlib.compress(hstr, compression_level)
                    payload = zlib.compress(payload, compression_level)
                if enc_comp_opts.get('encryption_key') is not None:
                    encryption_key = enc_comp_opts.get('encryption_key')
                    (hstr, payload, nonce) = \
                        encrypt(hstr, payload, encryption_key)

            # print(f'Adding {entry.get("url")} to IPFS')
            ipfs_hashes = push_to_ipfs(hstr, payload)

            if ipfs_hashes is None:
                log_error('Skipping ' +
                          record.rec_headers.get_header('WARC-Target-URI'))

                continue

            (http_header_ipfs_hash, payload_ipfs_hash) = ipfs_hashes

            original_uri = record.rec_headers.get_header('WARC-Target-URI')
            original_uri_surted = \
                surt.surt(original_uri,
                          path_strip_trailing_slash_unless_empty=False)
            timestamp = iso8601_to_digits14(
                record.rec_headers.get_header('WARC-Date'))
            mime = record.http_headers.get_header('content-type')
            obj = {
                'locator':
                    f'urn:ipfs/{http_header_ipfs_hash}/{payload_ipfs_hash}',
                'status_code': status_code,
                'mime_type': mime or '',
                'original_uri': original_uri
            }
            if enc_comp_opts.get('encryption_key') is not None:
                obj['encryption_key'] = enc_comp_opts.get('encryption_key')
                obj['encryption_method'] = 'aes'
                obj['encryption_nonce'] = nonce
            if title is not None:
                obj['title'] = title

            obj_jSON = json.dumps(obj)

            cdxj_line = f'{original_uri_surted} {timestamp} {obj_jSON}'
            cdxj_lines.append(cdxj_line)  # + '\n'
        return cdxj_lines


def generate_cdxj_metadata(cdxj_lines=None):
    metadata = ['!context ["https://tools.ietf.org/html/rfc7089"]']
    meta_vals = {
        'generator': f'InterPlanetary Wayback {ipwb_version}',
        'created_at': datetime.datetime.now().isoformat()
    }
    meta_vals = f'!meta {json.dumps(meta_vals)}'
    metadata.append(meta_vals)

    return metadata


def ask_user_for_encryption_key():
    if DEBUG:  # Allows testing instead of requiring a user prompt
        return 'ipwb'

    output_redirected = os.fstat(0) != os.fstat(1)
    prompt_string = 'Enter a key for encryption: '
    if output_redirected:  # Prevents prompt in redir output
        log_error(prompt_string, end='')
        prompt_string = ''

    key = input(prompt_string)

    return key


def verify_daemon_is_alive(host_and_port):
    """Ensure that the IPFS daemon is running via HTTP before proceeding"""
    try:
        requests.get(f'http://{host_and_port}')
    except ConnectionError:
        print(f'Daemon is not running at http://{host_and_port}')
        sys.exit()


def verify_file_exists(warc_path):
    if os.path.isfile(warc_path):
        return
    log_error(f'File at {warc_path} does not exist!')
    sys.exit()


def show_progress(msg, i, n):
    line = f'{msg}: {i}/{n}'
    print(line, file=sys.stderr, end='\r')
    # Clear status line, show complete msg
    if i == n - 1:
        final_msg = f'{msg} complete'
        space_delta = len(final_msg) - len(msg)
        spaces = '' * space_delta if space_delta > 0 else ''
        print(final_msg + spaces, file=sys.stderr, end='\r\n')


def log_error(err_in, end='\n'):
    print(err_in, file=sys.stderr, end=end)


def pull_from_ipfs(hash_in):
    return ipfs_client().cat(hash_in)


def push_bytes_to_ipfs(bytes_in):
    """
    Call the IPFS API to add the byte string to IPFS.
    When IPFS returns a hash, return this to the caller
    """
    # Returns unicode in py2.7, str in py3.7
    try:
        res = ipfs_client().add_bytes(bytes_in)  # bytes)
    except TypeError as _:
        print('fail')
        log_error('IPFS_API had an issue pushing the item to IPFS')
        log_error(sys.exc_info())
        log_error(len(bytes_in))
        traceback.print_tb(sys.exc_info()[-1])
    except ipfsapi.exceptions.ConnectionError as _:
        print('ConnErr')
        log_error(sys.exc_info())
        traceback.print_tb(sys.exc_info()[-1])
        return

    # TODO: verify that the add was successful

    if type(res).__name__ == 'unicode':
        return res
    elif type(res).__name__ == 'str':
        return res

    log_error('NEITHER UNICODE NOR STR RETURNED.')
    return res[0]['Hash']


def write_file(filename, content):
    with open(filename, 'w') as tmp_file:
        tmp_file.write(content)
