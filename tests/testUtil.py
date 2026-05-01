import os
import random
import string
import re
import tempfile

from time import sleep

from ipwb import replay
from ipwb import indexer
from ipwb import __file__ as moduleLocation

from multiprocessing import Process
from pathlib import Path

p = Process()


def createUniqueWARC():
    lines = []
    warc_in_filename = 'frogTest.warc'
    warc_in_path = os.path.join(
        Path(os.path.dirname(__file__)).parent,
        'samples', 'warcs', warc_in_filename)

    string_to_change = b'abcdefghijklmnopqrstuvwxz'
    random_string = get_random_string(len(string_to_change))
    random_bytes = str.encode(random_string)

    with open(warc_in_path, 'rb') as warcFile:
        newContent = warcFile.read().replace(string_to_change, random_bytes)

    warc_out_filename = warc_in_filename.replace('.warc',
                                                 f'_{random_string}.warc')
    warc_out_path = os.path.join(
        Path(os.path.dirname(__file__)).parent,
        'samples', 'warcs', warc_out_filename)

    print(warc_out_path)
    with open(warc_out_path, 'wb') as warcFile:
        warcFile.write(newContent)

    return warc_out_path


def get_random_string(n):
    return ''.join(random.SystemRandom().choice(
                   string.ascii_lowercase + string.digits) for _ in range(n))


def count_cdxj_entries(cdxj_data):
    urim_count = 0
    lines = cdxj_data.strip().split('\n')
    for line in lines:
        if line[0] != '!':  # Exclude metadata from count
            urim_count += 1
    return urim_count


def start_replay(warc_filename):
    global p
    path_of_warc = os.path.join(
        Path(os.path.dirname(__file__)).parent,
        'samples', 'warcs', warc_filename)

    fh, tempfile_path = tempfile.mkstemp(suffix='.cdxj')
    os.close(fh)

    p = Process(target=replay.start, args=[tempfile_path])
    p.start()
    sleep(5)

    cdxj_list = indexer.index_file_at(path_of_warc, quiet=True)
    cdxj = '\n'.join(cdxj_list)

    with open(tempfile_path, 'w') as f:
        f.write(cdxj)


def stop_replay():
    global p
    p.terminate()


def extract_relation_entries_from_link_timemap(tm):
    matches = re.findall('rel=".*?"', tm)
    matches = map(lambda s: s[5:-1], matches)
    return matches
