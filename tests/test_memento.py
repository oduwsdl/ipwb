import pytest

from . import testUtil as ipwb_test
from ipwb import replay
from ipwb import indexer
from ipwb import __file__ as moduleLocation
from time import sleep
import os
import subprocess
from urllib.request import urlopen
import requests
import random
import string
import re
import sys


def get_urims_from_timemap_in_warc(warcFilename):
    ipwb_test.start_replay(warcFilename)

    tm_uri = 'http://localhost:2016/timemap/link/memento.us/'
    tm = urlopen(tm_uri).read().decode('utf-8')

    urims = []
    for line in tm.split('\n'):
        is_a_memento = len(re.findall('rel=".*memento"', line)) > 0
        if is_a_memento:
            urims.append(re.findall('<(.*)>', line)[0])

    ipwb_test.stop_replay()

    return urims


def get_rels_from_urims_in_warc(warc):
    urims = get_urims_from_timemap_in_warc(warc)
    ipwb_test.start_replay(warc)

    # Get Link header values for each memento
    link_headers = []
    for urim in urims:
        link_headers.append(urlopen(urim).info().get('Link'))
    ipwb_test.stop_replay()

    rels_for_urims = []
    for link_header in link_headers:
        relForURIM = ipwb_test.extract_relation_entries_from_link_timemap(
            link_header)
        rels_for_urims.append(relForURIM)

    ipwb_test.stop_replay()
    return rels_for_urims


@pytest.mark.parametrize("warc,lookup,acceptdatetime,status", [
    ('5mementos.warc', 'timegate/memento.us',
     'Thu, 31 May 2007 20:35:00 GMT', 302),
    ('5mementos.warc', 'timegate/memento.us',
     'Thu, 31 May 2007 20:35:00', 400),
    ('5mementos.warc', 'timegate/memento.us',
     'Thu, 31 May 2007 20:35 GMT', 400),
    ('5mementos.warc', 'timegate/memento.us',
     '20181001123636', 400)
])
def test_acceptdatetime_status(warc, lookup, acceptdatetime, status):
    ipwb_test.start_replay(warc)

    headers = {'Accept-Datetime': acceptdatetime}

    resp = requests.get(f'http://localhost:2016/{lookup}',
                        allow_redirects=False, headers=headers)
    assert resp.status_code == status

    ipwb_test.stop_replay()


def test_mementoRelations_one():
    rels_for_urims = get_rels_from_urims_in_warc('1memento.warc')

    rels_for_urims = list(filter(lambda k: 'memento' in k, rels_for_urims[0]))
    m1_m1 = rels_for_urims[0].split(' ')

    onlyOneMemento = len(rels_for_urims) == 1

    cond_first_memento = 'first' in m1_m1
    cond_last_memento = 'last' in m1_m1

    assert onlyOneMemento and \
        cond_first_memento and \
        cond_last_memento


def test_mementoRelations_two():
    rels_for_urims = get_rels_from_urims_in_warc('2mementos.warc')

    cond_first_memento = False
    cond_last_next_memento = False
    cond_first_prev_memento = False
    cond_last_memento = False

    rels_for_urims1of2 = list(filter(
        lambda k: 'memento' in k, rels_for_urims[0]))
    rels_for_urims2of2 = list(filter(
        lambda k: 'memento' in k, rels_for_urims[1]))

    # mX_mY = URI-M requested, Y-th URIM-M in header
    m1_m1 = rels_for_urims1of2[0].split(' ')
    m1_m2 = rels_for_urims1of2[1].split(' ')
    m2_m1 = rels_for_urims2of2[0].split(' ')
    m2_m2 = rels_for_urims2of2[1].split(' ')

    cond_first_memento = 'first' in m1_m1
    cond_last_next_memento = 'last' in m1_m2 and 'next' in m1_m2
    cond_first_prev_memento = 'first' in m2_m1 and 'prev' in m2_m1
    cond_last_memento = 'last' in m2_m2

    assert cond_first_memento and \
        cond_last_next_memento and \
        cond_first_prev_memento and \
        cond_last_memento


def test_mementoRelations_three():
    rels_for_urims = get_rels_from_urims_in_warc('3mementos.warc')

    cond_m1m1_first_memento = False
    cond_m1m2_next_memento = False
    cond_m1m3_last_memento = False
    cond_m2m1_first_prev_memento = False
    cond_m2m2_memento = False
    cond_m2m3_last_next_memento = False
    cond_m3m1_first_memento = False
    cond_m3m2_prev_memento = False
    cond_m3m3_last_memento = False

    rels_for_urims1of3 = list(filter(
        lambda k: 'memento' in k, rels_for_urims[0]))
    rels_for_urims2of3 = list(filter(
        lambda k: 'memento' in k, rels_for_urims[1]))
    rels_for_urims3of3 = list(filter(
        lambda k: 'memento' in k, rels_for_urims[2]))

    # mX_mY = URI-M requested, Y-th URIM-M in header
    m1_m1 = rels_for_urims1of3[0].split(' ')
    m1_m2 = rels_for_urims1of3[1].split(' ')
    m1_m3 = rels_for_urims1of3[2].split(' ')
    m2_m1 = rels_for_urims2of3[0].split(' ')
    m2_m2 = rels_for_urims2of3[1].split(' ')
    m2_m3 = rels_for_urims2of3[2].split(' ')
    m3_m1 = rels_for_urims3of3[0].split(' ')
    m3_m2 = rels_for_urims3of3[1].split(' ')
    m3_m3 = rels_for_urims3of3[2].split(' ')

    cond_m1m1_first_memento = 'first' in m1_m1
    cond_m1m2_next_memento = 'next' in m1_m2
    cond_m1m3_last_memento = 'last' in m1_m3
    cond_m2m1_first_prev_memento = 'first' in m2_m1 and 'prev' in m2_m1
    cond_m2m2_memento = len(m2_m2) == 1
    cond_m2m3_last_next_memento = 'last' in m2_m3 and 'next' in m2_m3
    cond_m3m1_first_memento = 'first' in m3_m1
    cond_m3m2_prev_memento = 'prev' in m3_m2
    cond_m3m3_last_memento = 'last' in m3_m3

    assert (cond_m1m1_first_memento and
            cond_m1m2_next_memento and
            cond_m1m3_last_memento and
            cond_m2m1_first_prev_memento and
            cond_m2m2_memento and
            cond_m2m3_last_next_memento and
            cond_m3m1_first_memento and
            cond_m3m2_prev_memento and
            cond_m3m3_last_memento)


def test_mementoRelations_four():
    rels_for_urims = get_rels_from_urims_in_warc('4mementos.warc')

    cond_m1m1_first_memento = False
    cond_m1m2_next_memento = False
    cond_m1m3 = False
    cond_m1m4_last_memento = False
    cond_m2m1_first_prev_memento = False
    cond_m2m2_memento = False
    cond_m2m3_next_memento = False
    cond_m2m4_last_memento = False
    cond_m3m1_first_memento = False
    cond_m3m2_prev_memento = False
    cond_m3m3_memento = False
    cond_m3m4_last_next_memento = False
    cond_m4m1_first_memento = False
    cond_m4m2 = False
    cond_m4m3_prev_memento = False
    cond_m4m4_last_memento = False

    rels_for_urims1of4 = list(filter(
        lambda k: 'memento' in k, rels_for_urims[0]))
    rels_for_urims2of4 = list(filter(
        lambda k: 'memento' in k, rels_for_urims[1]))
    rels_for_urims3of4 = list(filter(
        lambda k: 'memento' in k, rels_for_urims[2]))
    rels_for_urims4of4 = list(filter(
        lambda k: 'memento' in k, rels_for_urims[3]))

    # mX_mY = URI-M requested, Y-th URIM-M in header
    m1_m1 = rels_for_urims1of4[0].split(' ')
    m1_m2 = rels_for_urims1of4[1].split(' ')
    # m1_m3 = rels_for_urims1of4[2].split(' ')
    m1_m4 = rels_for_urims1of4[2].split(' ')
    m2_m1 = rels_for_urims2of4[0].split(' ')
    m2_m2 = rels_for_urims2of4[1].split(' ')
    m2_m3 = rels_for_urims2of4[2].split(' ')
    m2_m4 = rels_for_urims2of4[3].split(' ')
    m3_m1 = rels_for_urims3of4[0].split(' ')
    m3_m2 = rels_for_urims3of4[1].split(' ')
    m3_m3 = rels_for_urims3of4[2].split(' ')
    m3_m4 = rels_for_urims3of4[3].split(' ')
    m4_m1 = rels_for_urims4of4[0].split(' ')
    # m4_m2 = rels_for_urims4of4[1].split(' ')
    m4_m3 = rels_for_urims4of4[1].split(' ')
    m4_m4 = rels_for_urims4of4[2].split(' ')

    cond_m1m1_first_memento = 'first' in m1_m1
    cond_m1m2_next_memento = 'next' in m1_m2
    # M3 not present
    cond_m1m4_last_memento = 'last' in m1_m4
    cond_m2m1_first_prev_memento = 'first' in m2_m1 and 'prev' in m2_m1
    cond_m2m2_memento = len(m2_m2) == 1
    cond_m2m3_next_memento = 'next' in m2_m3
    cond_m2m4_last_memento = 'last' in m2_m4
    cond_m3m1_first_memento = 'first' in m3_m1
    cond_m3m2_prev_memento = 'prev' in m3_m2
    cond_m3m3_memento = len(m3_m3) == 1
    cond_m3m4_last_next_memento = 'last' in m3_m4 and 'next' in m3_m4
    cond_m4m1_first_memento = 'first' in m4_m1
    # M2 not present
    cond_m4m3_prev_memento = 'prev' in m4_m3
    cond_m4m4_last_memento = 'last' in m4_m4

    assert (cond_m1m1_first_memento and
            cond_m1m2_next_memento and
            # cond_m1m3 and
            cond_m1m4_last_memento and
            cond_m2m1_first_prev_memento and
            cond_m2m2_memento and
            cond_m2m3_next_memento and
            cond_m2m4_last_memento and
            cond_m3m1_first_memento and
            cond_m3m2_prev_memento and
            cond_m3m3_memento and
            cond_m3m4_last_next_memento and
            cond_m4m1_first_memento and
            # cond_m4m2 and
            cond_m4m3_prev_memento and
            cond_m4m4_last_memento)


def test_mementoRelations_five():
    rels_for_urims = get_rels_from_urims_in_warc('5mementos.warc')

    cond_m1m1_first_memento = False
    cond_m1m2_next_memento = False
    cond_m1m3 = False
    cond_m1m4 = False
    cond_m1m5_last_memento = False
    cond_m2m1_first_prev_memento = False
    cond_m2m2_memento = False
    cond_m2m3_next_memento = False
    cond_m2m4 = False
    cond_m2m5_last_memento = False
    cond_m3m1_first_memento = False
    cond_m3m2_prev_memento = False
    cond_m3m3_memento = False
    cond_m3m4_next_memento = False
    cond_m3m5_last_memento = False
    cond_m4m1_first_memento = False
    cond_m4m2 = False
    cond_m4m3_prev_memento = False
    cond_m4m4_memento = False
    cond_m4m5_last_next_memento = False
    cond_m5m1_first_memento = False
    cond_m5m2 = False
    cond_m5m3 = False
    cond_m5m4_prev_memento = False
    cond_m5m5_last_memento = False

    rels_for_urims1of5 = list(filter(
        lambda k: 'memento' in k, rels_for_urims[0]))
    rels_for_urims2of5 = list(filter(
        lambda k: 'memento' in k, rels_for_urims[1]))
    rels_for_urims3of5 = list(filter(
        lambda k: 'memento' in k, rels_for_urims[2]))
    rels_for_urims4of5 = list(filter(
        lambda k: 'memento' in k, rels_for_urims[3]))
    rels_for_urims5of5 = list(filter(
        lambda k: 'memento' in k, rels_for_urims[4]))

    # mX_mY = URI-M requested, Y-th URIM-M in header
    m1_m1 = rels_for_urims1of5[0].split(' ')
    m1_m2 = rels_for_urims1of5[1].split(' ')
    # M3 not present
    # M4 not present
    m1_m5 = rels_for_urims1of5[2].split(' ')
    m2_m1 = rels_for_urims2of5[0].split(' ')
    m2_m2 = rels_for_urims2of5[1].split(' ')
    m2_m3 = rels_for_urims2of5[2].split(' ')
    # M4 not present
    m2_m5 = rels_for_urims2of5[3].split(' ')
    m3_m1 = rels_for_urims3of5[0].split(' ')
    m3_m2 = rels_for_urims3of5[1].split(' ')
    m3_m3 = rels_for_urims3of5[2].split(' ')
    m3_m4 = rels_for_urims3of5[3].split(' ')
    m3_m5 = rels_for_urims3of5[4].split(' ')
    m4_m1 = rels_for_urims4of5[0].split(' ')
    # M2 not present
    m4_m3 = rels_for_urims4of5[1].split(' ')
    m4_m4 = rels_for_urims4of5[2].split(' ')
    m4_m5 = rels_for_urims4of5[3].split(' ')
    m5_m1 = rels_for_urims5of5[0].split(' ')
    # M2 not present
    # M3 not present
    m5_m4 = rels_for_urims5of5[1].split(' ')
    m5_m5 = rels_for_urims5of5[2].split(' ')

    cond_m1m1_first_memento = 'first' in m1_m1
    cond_m1m2_next_memento = 'next' in m1_m2
    # M3 not present
    # M4 not present
    cond_m1m5_last_memento = 'last' in m1_m5
    cond_m2m1_first_prev_memento = 'first' in m2_m1 and 'prev' in m2_m1
    cond_m2m2_memento = len(m2_m2) == 1
    cond_m2m3_next_memento = 'next' in m2_m3
    # M4 not present
    cond_m2m5_last_memento = 'last' in m1_m5
    cond_m3m1_first_memento = 'first' in m3_m1
    cond_m3m2_prev_memento = 'prev' in m3_m2
    cond_m3m3_memento = len(m3_m3) == 1
    cond_m3m4_next_memento = 'next' in m3_m4
    cond_m3m5_last_memento = 'last' in m3_m5
    cond_m4m1_first_memento = 'first' in m4_m1
    # M2 not present
    cond_m4m3_prev_memento = 'prev' in m4_m3
    cond_m4m4_memento = len(m4_m4) == 1
    cond_m4m5_last_next_memento = 'last' in m4_m5 and 'next' in m4_m5
    cond_m5m1_first_memento = 'first' in m4_m1
    # M2 not present
    # M3 not present
    cond_m5m4_prev_memento = 'prev' in m5_m4
    cond_m5m5_last_memento = 'last' in m5_m5

    assert (cond_m1m1_first_memento and
            cond_m1m2_next_memento and
            # cond_m1m3 and
            # cond_m1m4 and
            cond_m1m5_last_memento and
            cond_m2m1_first_prev_memento and
            cond_m2m2_memento and
            cond_m2m3_next_memento and
            # cond_m2m4 and
            cond_m2m5_last_memento and
            cond_m3m1_first_memento and
            cond_m3m2_prev_memento and
            cond_m3m3_memento and
            cond_m3m4_next_memento and
            cond_m3m5_last_memento and
            cond_m4m1_first_memento and
            # cond_m4m2 and
            cond_m4m3_prev_memento and
            cond_m4m4_memento and
            cond_m4m5_last_next_memento and
            cond_m5m1_first_memento and
            # cond_m5m2 and
            # cond_m5m3 and
            cond_m5m4_prev_memento and
            cond_m5m5_last_memento)
