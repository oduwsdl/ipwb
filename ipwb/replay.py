#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
InterPlanetary Wayback Replay system

This script handles requests to replay IPWB archived contents based on a
supplied CDXJ file. This file has been previously generated by the ipwb
indexer. An interface is supplied when first started to assist the user in
navigating their captures.
"""

from __future__ import print_function
import sys
import os
import ipfsapi
import json
import subprocess
import pkg_resources
import surt
import re
import signal
import random
import string

from pywb.utils.canonicalize import unsurt

from flask import Flask
from flask import Response
from flask import request
from flask import redirect
from flask import abort

from ipfsapi.exceptions import StatusError as hashNotInIPFS
from bisect import bisect_left
from socket import gaierror
from socket import error as socketerror
from urlparse import urlsplit, urlunsplit  # N/A in Py3!

from requests.exceptions import HTTPError

import util as ipwbUtils
from util import IPFSAPI_HOST, IPFSAPI_PORT, IPWBREPLAY_HOST, IPWBREPLAY_PORT
from util import INDEX_FILE

import indexer

from base64 import b64decode
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

import base64

from werkzeug.routing import BaseConverter
from __init__ import __version__ as ipwbVersion


from flask import flash, url_for
from werkzeug.utils import secure_filename
from flask import send_from_directory

UPLOAD_FOLDER = '/tmp'
ALLOWED_EXTENSIONS = ('.warc', '.warc.gz')

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.debug = False

IPFS_API = ipfsapi.Client(IPFSAPI_HOST, IPFSAPI_PORT)


@app.after_request
def setServerHeader(response):
    response.headers['Server'] = 'InterPlanetary Wayback Replay/' + ipwbVersion
    return response


def allowed_file(filename):
    return filename.lower().endswith(ALLOWED_EXTENSIONS)


@app.route('/upload', methods=['POST'])
def upload_file():
    # check if the post request has the file part
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    file = request.files['file']
    # if user does not select file, browser also
    # submit an empty part without filename
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        warcPath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(warcPath)

        # TODO: Check if semaphore lock exists, alert user if so, wait
        # Index file, produce new.cdxj
        #print('Indexing file from uploaded WARC at {0} to {1}'.format(
        #    warcPath, cdxjPath))
        indexer.indexFileAt(warcPath, outfile=app.cdxjFilePath)
        print('Index updated at {0}'.format(app.cdxjFilePath))

        # TODO: Create semaphore lock
        # Join current.cdxj w/ new.cdxj, write to combined.cdxj

        print('Setting ipwb replay index variables')

        # TODO: Release semaphore lock

        return redirect('/')


@app.route('/webui/<path:path>')
def showWebUI(path):
    """ Handle requests for the IPWB replay Web interface and requests
        for initializing the replay ServiceWorker.
    """
    webuiPath = '/'.join(('webui', path)).replace('ipwb.replay', 'ipwb')
    content = pkg_resources.resource_string(__name__, webuiPath)

    if 'index.html' in path:
        iFile = ipwbUtils.getIPWBReplayIndexPath()

        if iFile is None or iFile == '':
            iFile = pkg_resources.resource_filename(__name__, INDEX_FILE)

        if not os.path.isabs(iFile):  # Convert rel to abs path
            iFileAbs = pkg_resources.resource_filename(__name__, iFile)
            if os.path.exists(iFileAbs):
                iFile = iFileAbs  # Local file

        (mCount, uniqueURIRs) = retrieveMemCount(iFile)
        content = content.replace(
            'MEMCOUNT', str(mCount))
        content = content.replace(
            'UNIQUE', str(uniqueURIRs))

        content = content.replace(
            'let uris = []',
            'let uris = {0}'.format(getURIsAndDatetimesInCDXJ(iFile)))
        content = content.replace('INDEXSRC', iFile)

    fileExtension = os.path.splitext(path)[1]

    mimeType = 'text/html'

    if fileExtension == '.js':
        mimeType = 'application/javascript'
    elif fileExtension == '.css':
        mimeType = 'text/css'

    resp = Response(content, mimetype=mimeType)
    resp.headers['Service-Worker-Allowed'] = '/'

    return resp


def getServiceWorker(path):
    """ Get the ServiceWorker code and return corresponding
        HTTP response information for the Worker
    """
    path = ('/' + path).replace('ipwb.replay', 'ipwb')
    content = pkg_resources.resource_string(__name__, path)
    resp = Response(content, mimetype='application/javascript')
    resp.headers['Service-Worker-Allowed'] = '/'
    return resp


class UnsupportedIPFSVersions(Exception):
    pass


@app.route('/daemon/<cmd>')
def commandDaemon(cmd):
    global IPFS_API
    if cmd == 'status':
        return generateDaemonStatusButton()
    elif cmd == 'start':
        subprocess.Popen(['ipfs', 'daemon'])
        # retString = 'Failed to start IPFS daemon'
        # if 'Daemon is ready' in check_output():
        #  retString = 'IPFS daemon started'
        return Response('IPFS daemon starting...')

    elif cmd == 'stop':
        try:
            installedIPFSVersion = IPFS_API.version()['Version']
            if ipwbUtils.compareVersions(installedIPFSVersion, '0.4.10') < 0:
                raise UnsupportedIPFSVersions()
            IPFS_API.shutdown()
        except (subprocess.CalledProcessError, UnsupportedIPFSVersions) as e:
            # go-ipfs < 0.4.10
            if os.name == 'nt':
                subprocess.call(['taskkill', '/im', 'ipfs.exe', '/F'])
            else:
                subprocess.call(['killall', 'ipfs'])

        return Response('IPFS daemon stopping...')
    else:
        print('ERROR, bad command sent to daemon API!')
        print(cmd)
        return Response('bad command!')


@app.route('/memento/*/')
def showMementosForURIRs_sansJS():
    urir = request.args.get('url')
    return redirect('/memento/*/' + urir, code=301)


@app.route('/memento/*/<path:urir>')
def showMementosForURIRs(urir):
    urir = getCompleteURI(urir)

    if ipwbUtils.isLocalHosty(urir):
        urir = urir.split('/', 4)[4]
    s = surt.surt(urir, path_strip_trailing_slash_unless_empty=False)
    indexPath = ipwbUtils.getIPWBReplayIndexPath()

    print('Getting CDXJ Lines with the URI-R {0} from {1}'
          .format(urir, indexPath))
    cdxjLinesWithURIR = getCDXJLinesWithURIR(urir, indexPath)

    if len(cdxjLinesWithURIR) == 1:
        fields = cdxjLinesWithURIR[0].split(' ', 2)
        redirectURI = '/memento/{1}/{0}'.format(unsurt(fields[0]), fields[1])
        return redirect(redirectURI, code=302)

    msg = ''
    if cdxjLinesWithURIR:
        msg += '<p>{0} capture(s) available:</p><ul>'.format(
            len(cdxjLinesWithURIR))
        for line in cdxjLinesWithURIR:
            fields = line.split(' ', 2)
            dt14 = fields[1]
            dtrfc1123 = ipwbUtils.digits14ToRFC1123(fields[1])
            msg += ('<li><a href="/{1}/{0}">{0} at {2}</a></li>'
                    .format(unsurt(fields[0]), dt14, dtrfc1123))
        msg += '</ul>'
    else:  # No captures for URI-R
        msg = generateNoMementosInterface_noDatetime(urir)

    return Response(msg)


class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]


app.url_map.converters['regex'] = RegexConverter


def resolveMemento(urir, datetime):
    """ Request a URI-R at a supplied datetime from the CDXJ """
    urir = getCompleteURI(urir)

    if ipwbUtils.isLocalHosty(urir):
        urir = urir.split('/', 4)[4]
    s = surt.surt(urir, path_strip_trailing_slash_unless_empty=False)
    indexPath = ipwbUtils.getIPWBReplayIndexPath()

    print('Getting CDXJ Lines with the URI-R {0} from {1}'
          .format(urir, indexPath))
    cdxjLinesWithURIR = getCDXJLinesWithURIR(urir, indexPath)

    closestLine = getCDXJLineClosestTo(datetime, cdxjLinesWithURIR)

    if closestLine is None:
        msg = '<h1>ERROR 404</h1>'
        msg += 'No capture found for {0} at {1}.'.format(urir, datetime)

        return Response(msg, status=404)

    uri = unsurt(closestLine.split(' ')[0])
    newDatetime = closestLine.split(' ')[1]

    linkHeader = getLinkHeaderAbbreviatedTimeMap(urir, newDatetime)

    return (newDatetime, linkHeader, uri)


@app.route('/memento/<regex("[0-9]{1,14}"):datetime>/<path:urir>')
def showMemento(urir, datetime):
    resolvedMemento = resolveMemento(urir, datetime)

    # resolved to a 404, flask Response object returned instead of tuple
    if isinstance(resolvedMemento, Response):
        return resolvedMemento
    (newDatetime, linkHeader, uri) = resolvedMemento

    if newDatetime != datetime:
        resp = redirect('/memento/{0}/{1}'.format(newDatetime, urir), code=302)
    else:
        resp = show_uri(uri, newDatetime)

    resp.headers['Link'] = linkHeader

    return resp


def getCDXJLineClosestTo(datetimeTarget, cdxjLines):
    """ Get the closest CDXJ entry for a datetime and URI-R """
    smallestDiff = float('inf')  # math.inf is only py3
    bestLine = None
    datetimeTarget = int(datetimeTarget)
    for cdxjLine in cdxjLines:
        dt = int(cdxjLine.split(' ')[1])
        diff = abs(dt - datetimeTarget)
        if diff < smallestDiff:
            smallestDiff = diff
            bestLine = cdxjLine
    return bestLine


def getCDXJLinesWithURIR(urir, indexPath):
    """ Get all CDXJ records corresponding to a URI-R """
    if not indexPath:
        indexPath = ipwbUtils.getIPWBReplayIndexPath()
    indexPath = getIndexFileFullPath(indexPath)

    print('Getting CDXJ Lines with {0} in {1}'.format(urir, indexPath))
    s = surt.surt(urir, path_strip_trailing_slash_unless_empty=False)
    cdxjLinesWithURIR = []

    cdxjLineIndex = getCDXJLine_binarySearch(s, indexPath, True, True)  # get i

    if cdxjLineIndex is None:
        return []

    cdxjLines = []
    with open(indexPath, 'r') as f:
        cdxjLines = f.read().split('\n')
        baseCDXJLine = cdxjLines[cdxjLineIndex]  # via binsearch

        cdxjLinesWithURIR.append(baseCDXJLine)

    # Get lines before pivot that match surt
    sI = cdxjLineIndex - 1
    while sI >= 0:
        if cdxjLines[sI].split(' ')[0] == s:
            cdxjLinesWithURIR.append(cdxjLines[sI])
        sI -= 1
    # Get lines after pivot that match surt
    sI = cdxjLineIndex + 1
    while sI < len(cdxjLines):
        if cdxjLines[sI].split(' ')[0] == s:
            cdxjLinesWithURIR.append(cdxjLines[sI])
        sI += 1
    return cdxjLinesWithURIR


@app.route('/timegate/<path:urir>')
def queryTimeGate(urir):
    adt = request.headers.get("Accept-Datetime")
    if adt is None:
        adt = ipwbUtils.getRFC1123OfNow()

    datetime14 = ipwbUtils.rfc1123ToDigits14(adt)

    resolvedMemento = resolveMemento(urir, datetime14)

    if isinstance(resolvedMemento, Response):
        return resolvedMemento
    (newDatetime, linkHeader, uri) = resolvedMemento

    resp = redirect('/memento/{0}/{1}'.format(newDatetime, urir), code=302)

    resp.headers['Link'] = linkHeader
    resp.headers['Vary'] = 'Accept-Datetime'

    return resp


@app.route('/timemap/<regex("link|cdxj"):format>/<path:urir>')
def showTimeMap(urir, format):
    urir = getCompleteURI(urir)
    s = surt.surt(urir, path_strip_trailing_slash_unless_empty=False)
    indexPath = ipwbUtils.getIPWBReplayIndexPath()

    cdxjLinesWithURIR = getCDXJLinesWithURIR(urir, indexPath)
    tmContentType = ''

    hostAndPort = ipwbUtils.getIPWBReplayConfig()

    tgURI = 'http://{0}:{1}/timegate/{2}'.format(
        hostAndPort[0],
        hostAndPort[1], urir)

    tm = ''  # Initialize for usage beyond below conditionals
    if format == 'link':
        tm = generateLinkTimeMapFromCDXJLines(
            cdxjLinesWithURIR, s, request.url, tgURI)
        tmContentType = 'application/link-format'
    elif format == 'cdxj':
        tm = generateCDXJTimeMapFromCDXJLines(
            cdxjLinesWithURIR, s, request.url, tgURI)
        tmContentType = 'application/cdxj+ors'

    resp = Response(tm)
    resp.headers['Content-Type'] = tmContentType

    return resp


def getLinkHeaderAbbreviatedTimeMap(urir, pivotDatetime):
    s = surt.surt(urir, path_strip_trailing_slash_unless_empty=False)
    indexPath = ipwbUtils.getIPWBReplayIndexPath()

    cdxjLinesWithURIR = getCDXJLinesWithURIR(urir, indexPath)
    hostAndPort = ipwbUtils.getIPWBReplayConfig()

    tgURI = 'http://{0}:{1}/timegate/{2}'.format(
        hostAndPort[0],
        hostAndPort[1], urir)

    tmURI = 'http://{0}:{1}/timemap/link/{2}'.format(
        hostAndPort[0],
        hostAndPort[1], urir)
    tm = generateLinkTimeMapFromCDXJLines(cdxjLinesWithURIR, s, tmURI, tgURI)

    # Fix base TM relation when viewing abbrev version in Link resp
    tm = tm.replace('rel="self timemap"', 'rel="timemap"')

    # Only one memento in TimeMap
    if 'rel="first last memento"' in tm:
        return tm.replace('\n', ' ').strip()

    tmLines = tm.split('\n')
    for idx, line in enumerate(tmLines):
        if len(re.findall('rel=.*memento"', line)) == 0:
            continue  # Not a memento

        if pivotDatetime in line:
            addBothNextAndPrev = False
            if idx > 0 and idx < len(tmLines) - 1:
                addBothNextAndPrev = True

            if addBothNextAndPrev or idx == 0:
                tmLines[idx + 1] = \
                    tmLines[idx + 1].replace('memento"', 'next memento"')
            if addBothNextAndPrev or idx == len(tmLines) - 1:
                tmLines[idx - 1] = \
                    tmLines[idx - 1].replace('memento"', 'prev memento"')
            break

    # Remove all mementos in abbrev TM that are not:
    #   first, last, prev, next, or pivot
    for idx, line in enumerate(tmLines):
        if len(re.findall('rel=.*memento"', line)) == 0:
            continue  # Not a memento
        if pivotDatetime in line:
            continue

        if len(re.findall('rel=.*(next|prev|first|last)', line)) == 0:
            tmLines[idx] = ''

    return ' '.join(filter(None, tmLines))


def getProxiedURIT(uriT):
    tmurl = list(urlsplit(uriT))
    if app.proxy is not None:
        # urlsplit put domain in path for "example.com"
        tmurl[1] = app.proxy  # Set replay host/port if no scheme
        proxyuri = urlsplit(app.proxy)
        if proxyuri.scheme != '':
            tmurl[0] = proxyuri.scheme
            tmurl[1] = proxyuri.netloc + proxyuri.path

    return tmurl


def generateLinkTimeMapFromCDXJLines(cdxjLines, original, tmself, tgURI):
    tmurl = getProxiedURIT(tmself)
    if app.proxy is not None:
        tmself = urlunsplit(tmurl)

    # Extract and trim for host:port prepending
    tmurl[2] = ''  # Clear TM path
    hostAndPort = urlunsplit(tmurl) + '/'

    # unsurted URI will never have a scheme, add one
    originalURI = 'http://{0}'.format(unsurt(original))

    tmData = '<{0}>; rel="original",\n'.format(originalURI)
    tmData += '<{0}>; rel="self timemap"; '.format(tmself)
    tmData += 'type="application/link-format",\n'

    cdxjTMURI = tmself.replace('/timemap/link/', '/timemap/cdxj/')
    tmData += '<{0}>; rel="timemap"; '.format(cdxjTMURI)
    tmData += 'type="application/cdxj+ors",\n'

    tmData += '<{0}>; rel="timegate"'.format(tgURI)

    for i, line in enumerate(cdxjLines):
        (surtURI, datetime, json) = line.split(' ', 2)
        dtRFC1123 = ipwbUtils.digits14ToRFC1123(datetime)
        firstLastStr = ''

        if len(cdxjLines) > 1:
            if i == 0:
                firstLastStr = 'first '
            elif i == len(cdxjLines) - 1:
                firstLastStr = 'last '
        elif len(cdxjLines) == 1:
            firstLastStr = 'first last '

        tmData += ',\n<{0}memento/{1}/{2}>; rel="{3}memento"; datetime="{4}"' \
                  .format(hostAndPort, datetime, unsurt(surtURI), firstLastStr,
                          dtRFC1123)
    return tmData + '\n'


def generateCDXJTimeMapFromCDXJLines(cdxjLines, original, tmself, tgURI):
    tmurl = getProxiedURIT(tmself)
    if app.proxy is not None:
        tmself = urlunsplit(tmurl)

    # unsurted URI will never have a scheme, add one
    originalURI = 'http://{0}'.format(unsurt(original))

    tmData = '!context ["http://tools.ietf.org/html/rfc7089"]\n'
    tmData += '!id {{"uri": "{0}"}}\n'.format(tmself)
    tmData += '!keys ["memento_datetime_YYYYMMDDhhmmss"]\n'
    tmData += '!meta {{"original_uri": "{0}"}}\n'.format(originalURI)
    tmData += '!meta {{"timegate_uri": "{0}"}}\n'.format(tgURI)
    linkTMURI = tmself.replace('/timemap/cdxj/', '/timemap/link/')
    tmData += ('!meta {{"timemap_uri": {{'
               '"link_format": "{0}", '
               '"cdxj_format": "{1}"'
               '}}}}\n').format(linkTMURI, tmself)
    hostAndPort = tmself[0:tmself.index('timemap/')]

    for i, line in enumerate(cdxjLines):
        (surtURI, datetime, json) = line.split(' ', 2)
        dtRFC1123 = ipwbUtils.digits14ToRFC1123(datetime)
        firstLastStr = ''

        if len(cdxjLines) > 1:
            if i == 0:
                firstLastStr = 'first '
            elif i == len(cdxjLines) - 1:
                firstLastStr = 'last '
        elif len(cdxjLines) == 1:
            firstLastStr = 'first last '

        tmData += ('{1} {{'
                   '"uri": "{0}memento/{1}/{2}", '
                   '"rel": "{3}memento", '
                   '"datetime"="{4}"}}\n').format(
                hostAndPort, datetime, unsurt(surtURI),
                firstLastStr, dtRFC1123)
    return tmData


# Fixes Flask issue of clipping queryString
def getCompleteURI(uri):
    qs = request.query_string.decode('utf-8')
    if qs != '':
        uri += '?' + qs
    return uri


@app.errorhandler(Exception)
def all_exception_handler(error):
    print(error)
    print(sys.exc_info())

    return 'Error', 500


# This route needs better restructuring but is currently only used to get the
# webUI location for the ipwb webUI, more setting might need to be fetched in
# the future.
@app.route('/config/<requestedSetting>')
def getRequestedSetting(requestedSetting):
    return Response(ipwbUtils.getIPFSAPIHostAndPort() + '/webui')


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def show_uri(path, datetime=None):
    global IPFS_API

    if len(path) == 0:
        return showWebUI('index.html')

    # TODO: Use a better approach to serve static contents
    # instead of using the same logic for every JS file as the SW script
    localScripts = ['serviceWorker.js',
                    'reconstructive.js',
                    'reconstructive-banner.js']
    if path in localScripts:
        return getServiceWorker(path)

    daemonAddress = '{0}:{1}'.format(IPFSAPI_HOST, IPFSAPI_PORT)
    if not ipwbUtils.isDaemonAlive(daemonAddress):
        errStr = ('IPFS daemon not running. '
                  'Start it using $ ipfs daemon on the command-line '
                  ' or from the <a href="/">'
                  'IPWB replay homepage</a>.')
        return Response(errStr, status=503)

    path = getCompleteURI(path)
    cdxjLine = ''
    try:
        surtedURI = surt.surt(
                     path, path_strip_trailing_slash_unless_empty=False)
        indexPath = ipwbUtils.getIPWBReplayIndexPath()

        searchString = surtedURI
        if datetime is not None:
            searchString = surtedURI + ' ' + datetime

        cdxjLine = getCDXJLine_binarySearch(searchString, indexPath)
        print('CDXJ Line: {0}'.format(cdxjLine))

    except Exception as e:
        print(sys.exc_info()[0])
        respString = ('{0} not found :(' +
                      ' <a href="http://{1}:{2}">Go home</a>').format(
            path, IPWBREPLAY_HOST, IPWBREPLAY_PORT)
        return Response(respString)
    if cdxjLine is None:  # Resource not found in archives
        return generateNoMementosInterface(path, datetime)

    cdxjParts = cdxjLine.split(" ", 2)
    jObj = json.loads(cdxjParts[2])
    datetime = cdxjParts[1]

    digests = jObj['locator'].split('/')

    class HashNotFoundError(Exception):
        pass

    payload = None
    header = None
    try:
        def handler(signum, frame):
            raise HashNotFoundError()

        if os.name != 'nt':  # Bug #310
            signal.signal(signal.SIGALRM, handler)
            signal.alarm(10)

        payload = IPFS_API.cat(digests[-1])
        header = IPFS_API.cat(digests[-2])

        if os.name != 'nt':  # Bug #310
            signal.alarm(0)

    except ipfsapi.exceptions.TimeoutError:
        print("{0} not found at {1}".format(cdxjParts[0], digests[-1]))
        respString = ('{0} not found in IPFS :(' +
                      ' <a href="http://{1}:{2}">Go home</a>').format(
            path, IPWBREPLAY_HOST, IPWBREPLAY_PORT)
        return Response(respString)
    except TypeError as e:
        print('A type error occurred')
        print(e)
        abort(500)
    except HTTPError as e:
        print("Fetching from the IPFS failed")
        print(e)
        abort(503)
    except HashNotFoundError:
        if payload is None:
            print("Hashes not found:\n\t{0}\n\t{1}".format(
                digests[-1], digests[-2]))
            abort(404)
        else:  # payload found but not header, fabricate header
            print("HTTP header not found, fabricating for resp replay")
            header = ''
    except Exception as e:
        print('Unknown exception occurred while fetching from ipfs.')
        print(e)
        abort(500)

    if 'encryption_method' in jObj:
        keyString = None
        while keyString is None:
            if 'encryption_key' in jObj:
                keyString = jObj['encryption_key']
            else:
                askForKey = ('Enter a path for file',
                             ' containing decryption key: \n> ')
                keyString = raw_input(askForKey)

        paddedEncryptionKey = pad(keyString, AES.block_size)
        key = base64.b64encode(paddedEncryptionKey)

        nonce = b64decode(jObj['encryption_nonce'])
        cipher = AES.new(key, AES.MODE_CTR, nonce=nonce)
        header = cipher.decrypt(base64.b64decode(header))
        payload = cipher.decrypt(base64.b64decode(payload))

    hLines = header.split('\n')
    hLines.pop(0)

    status = 200
    if 'status_code' in jObj:
        status = jObj['status_code']

    resp = Response(payload, status=status)

    for idx, hLine in enumerate(hLines):
        k, v = hLine.split(': ', 1)

        if k.lower() == 'transfer-encoding' and v.lower() == 'chunked':
            try:
                unchunkedPayload = extractResponseFromChunkedData(payload)
            except Exception as e:
                continue  # Data may have no actually been chunked
            resp.set_data(unchunkedPayload)

        if k.lower() not in ["content-type", "content-encoding", "location"]:
            k = "X-Archive-Orig-" + k

        resp.headers[k] = v

    # Add ipwb header for additional SW logic
    newPayload = resp.get_data()
    ipwbjsinject = """<script src="/webui/webui.js"></script>
                      <script>injectIPWBJS()</script>"""
    newPayload = newPayload.replace('</html>', ipwbjsinject + '</html>')
    resp.set_data(newPayload)

    resp.headers['Memento-Datetime'] = ipwbUtils.digits14ToRFC1123(datetime)

    if header is None:
        resp.headers['X-Headers-Generated-By'] = 'InterPlanetary Wayback'

    # Get TimeMap for Link response header
    # respWithLinkHeader = getLinkHeaderAbbreviatedTimeMap(path, datetime)
    # resp.headers['Link'] = respWithLinkHeader.replace('\n', ' ')

    if status[0] == '3' and isUri(resp.headers.get('Location')):
        # Bad assumption that the URI-M will contain \d14 but works for now.
        uriBeforeURIR = request.url[:re.search(r'/\d{14}/', request.url).end()]
        newURIM = uriBeforeURIR + resp.headers['Location']
        resp.headers['Location'] = newURIM

    return resp


def isUri(str):
    return re.match('^https?://', str, flags=re.IGNORECASE)


def generateNoMementosInterface_noDatetime(urir):
    msg = '<h1>ERROR 404</h1>'
    msg += 'No capture(s) found for {0}.'.format(urir)

    msg += ('<form method="get" action="/memento/*/" '
            'style="margin-top: 1.0em;">'
            '<input type="text" value="{0}" id="url"'
            'name="url" aria-label="Enter a URI" />'
            '<input type="submit" value="Search URL in the archive"/>'
            '</form>').format(urir)

    return msg


def generateNoMementosInterface(path, datetime):
    msg = '<h1>ERROR 404</h1>'
    msg += 'No capture found for {0} at {1}.'.format(path, datetime)

    linesWithSameURIR = getCDXJLinesWithURIR(path, None)
    print('CDXJ lines with URI-R at {0}'.format(path))
    print(linesWithSameURIR)

    # TODO: Use closest instead of conditioning on single entry
    #  temporary fix for core functionality in #225
    if len(linesWithSameURIR) == 1:
        fields = linesWithSameURIR[0].split(' ', 2)
        redirectURI = '/{1}/{0}'.format(unsurt(fields[0]), fields[1])
        return redirect(redirectURI, code=302)

    urir = ''
    if linesWithSameURIR:
        msg += '<p>{0} capture(s) available:</p><ul>'.format(
            len(linesWithSameURIR))
        for line in linesWithSameURIR:
            fields = line.split(' ', 2)
            urir = unsurt(fields[0])
            msg += ('<li><a href="/{1}/{0}">{0} at {1}</a></li>'
                    .format(urir, fields[1]))
        msg += '</ul>'

    msg += '<p>TimeMaps: '
    msg += '<a href="/timemap/link/{0}">Link</a> '.format(urir)
    msg += '<a href="/timemap/cdxj/{0}">CDXJ</a> '.format(urir)

    resp = Response(msg, status=404)
    linkHeader = getLinkHeaderAbbreviatedTimeMap(path, datetime)

    # By default, a TM has a self-reference URI-T
    linkHeader = linkHeader.replace('self timemap', 'timemap')

    resp.headers['Link'] = linkHeader

    return resp


def extractResponseFromChunkedData(data):
    chunkDescriptor = -1
    retStr = ''

    (chunkDescriptor, rest) = data.split('\n', 1)
    chunkDescriptor = chunkDescriptor.split(';')[0].strip()

    while chunkDescriptor != '0':
        # On fail, exception, delta in header vs. payload chunkedness
        chunkDecFromHex = int(chunkDescriptor, 16)  # Get dec for slice
        retStr += rest[:chunkDecFromHex]  # Add to payload
        rest = rest[chunkDecFromHex:]  # Trim from the next chunk onward
        (CRLF, chunkDescriptor, rest) = rest.split('\n', 2)
        chunkDescriptor = chunkDescriptor.split(';')[0].strip()

        if len(chunkDescriptor.strip()) == 0:
            break
    return retStr


def generateDaemonStatusButton():
    text = 'Not Running'
    buttonText = 'Start'
    if ipwbUtils.isDaemonAlive():
        text = 'Running'
        buttonText = 'Stop'

    statusPageHTML = '<html id="status{0}" class="status">'.format(buttonText)
    statusPageHTML += ('<head><base href="/webui/" /><link rel="stylesheet" '
                       'type="text/css" href="webui.css" />'
                       '<script src="webui.js"></script>'
                       '<script src="daemonController.js"></script>'
                       '</head><body>')
    buttonHTML = '<span id="status">{0}</span>'.format(text)
    buttonHTML += '<button id="daeAction">{0}</button>'.format(buttonText)

    footer = '<script>assignStatusButtonHandlers()</script></body></html>'
    return Response('{0}{1}{2}'.format(statusPageHTML, buttonHTML, footer))


def fetchRemoteCDXJFile(path):
    fileContents = ''
    path = path.replace('ipfs://', '')
    # TODO: Take into account /ipfs/(hash), first check if this is correct fmt

    if '://' not in path:  # isAIPFSHash
        # TODO: Check if a valid IPFS hash
        print('No scheme in path, assuming IPFS hash and fetching...')
        try:
            print("Trying to ipfs.cat('{0}')".format(path))
            dataFromIPFS = IPFS_API.cat(path)
        except hashNotInIPFS:
            print(("The CDXJ at hash {0} could"
                   " not be found in IPFS").format(path))
            sys.exit()
        except Exception as e:
            print("An error occurred with ipfs.cat")
            print(sys.exc_info()[0])
            sys.exit()
        print('Data successfully obtained from IPFS')
        return dataFromIPFS
    else:  # http://, ftp://, smb://, file://
        print('Path contains a scheme, fetching remote file...')
        fileContents = ipwbUtils.fetchRemoteFile(path)
        return fileContents

    # TODO: Check if valid CDXJ here before returning
    return fileContents


def getIndexFileContents(cdxjFilePath=INDEX_FILE):
    if not os.path.exists(cdxjFilePath):
        print('File {0} does not exist locally, fetching remote'.format(
                                                                 cdxjFilePath))
        return fetchRemoteCDXJFile(cdxjFilePath) or ''

    indexFilePath = '/{0}'.format(cdxjFilePath).replace('ipwb.replay', 'ipwb')
    print('getting index file at {0}'.format(indexFilePath))

    indexFileContent = ''
    with open(cdxjFilePath, 'r') as f:
        indexFileContent = f.read()

    return indexFileContent


def getIndexFileFullPath(cdxjFilePath=INDEX_FILE):
    indexFilePath = '/{0}'.format(cdxjFilePath).replace('ipwb.replay', 'ipwb')

    if os.path.isfile(cdxjFilePath):
        return cdxjFilePath

    indexFileName = pkg_resources.resource_filename(__name__, indexFilePath)
    return indexFileName


def getURIsAndDatetimesInCDXJ(cdxjFilePath=INDEX_FILE):
    indexFileContents = getIndexFileContents(cdxjFilePath)

    if not indexFileContents:
        return 0

    lines = indexFileContents.strip().split('\n')

    uris = {}
    for i, l in enumerate(lines):
        if not indexer.isValidCDXJLine(l):
            continue

        if indexer.isCDXJMetadataRecord(l):
            continue

        cdxjFields = l.split(' ', 2)
        uri = unsurt(cdxjFields[0])
        datetime = cdxjFields[1]

        try:
            jsonFields = json.loads(cdxjFields[2])
        except Exception as e:  # Skip lines w/o JSON block
            continue

        if uri not in uris:
            uris[uri] = {}
            uris[uri]['datetimes'] = []
        uris[uri]['datetimes'].append(datetime)
        uris[uri]['mime'] = jsonFields['mime_type']

        pass
    return json.dumps(uris)


def retrieveMemCount(cdxjFilePath=INDEX_FILE):
    print("Retrieving URI-Ms from {0}".format(cdxjFilePath))
    indexFileContents = getIndexFileContents(cdxjFilePath)

    errReturn = (0, 0)

    if not indexFileContents:
        return errReturn
    lines = indexFileContents.strip().split('\n')

    if not lines:
        return errReturn
    mementoCount = 0

    bucket = {}
    for i, l in enumerate(lines):
        validCDXJLine = indexer.isValidCDXJLine(l)
        metadataRecord = indexer.isCDXJMetadataRecord(l)
        if validCDXJLine and not metadataRecord:
            mementoCount += 1
            surtURI = l.split()[0]
            if surtURI not in bucket:
                bucket[surtURI] = 1
            else:  # Unnecessary to keep count now, maybe useful later
                bucket[surtURI] += 1

    return mementoCount, len(bucket.keys())


def objectifyCDXJData(lines, onlyURI):
    cdxjData = {'metadata': [], 'data': []}
    for line in lines:
        if len(line.strip()) == 0:
            break
        if line[0] != '!':
            (surt, datetime, theRest) = line.split(' ', 2)
            searchString = "{0} {1}".format(surt, datetime)
            if onlyURI:
                searchString = surt
            cdxjData['data'].append(searchString)
        else:
            cdxjData['metadata'].append(line)
    return cdxjData


def binary_search(haystack, needle, returnIndex=False, onlyURI=False):
    lBound = 0
    uBound = None

    surtURIsAndDatetimes = []

    cdxjObj = objectifyCDXJData(haystack, onlyURI)
    surtURIsAndDatetimes = cdxjObj['data']

    metaLineCount = len(cdxjObj['metadata'])

    if uBound is not None:
        uBound = uBound
    else:
        uBound = len(surtURIsAndDatetimes)

    pos = bisect_left(surtURIsAndDatetimes, needle, lBound, uBound)

    if pos != uBound and surtURIsAndDatetimes[pos] == needle:
        if returnIndex:  # Index useful for adjacent line searching
            return pos + metaLineCount
        return haystack[pos + metaLineCount]
    else:
        return None


def getCDXJLine_binarySearch(
         surtURI, cdxjFilePath=INDEX_FILE, retIndex=False, onlyURI=False):
    fullFilePath = getIndexFileFullPath(cdxjFilePath)

    with open(fullFilePath, 'r') as cdxjFile:
        lines = cdxjFile.read().split('\n')

        lineFound = binary_search(lines, surtURI, retIndex, onlyURI)
        if lineFound is None:
            print("Could not find {0} in CDXJ at {1}".format(
                surtURI, fullFilePath))

        return lineFound


def start(cdxjFilePath, proxy=None):
    hostPort = ipwbUtils.getIPWBReplayConfig()
    app.proxy = proxy

    if not hostPort:
        ipwbUtils.setIPWBReplayConfig(IPWBREPLAY_HOST, IPWBREPLAY_PORT)
        hostPort = ipwbUtils.getIPWBReplayConfig()

    if ipwbUtils.isDaemonAlive():
        ipwbUtils.setIPWBReplayIndexPath(cdxjFilePath)
        app.cdxjFilePath = cdxjFilePath
    else:
        print('Sample data not pulled from IPFS.')
        print('Check that the IPFS daemon is running.')

    try:
        print('IPWB replay started on http://{0}:{1}'.format(
            IPWBREPLAY_HOST, IPWBREPLAY_PORT
        ))
        app.run(host='0.0.0.0', port=IPWBREPLAY_PORT)
    except gaierror:
        print('Detected no active Internet connection.')
        print('Overriding to use default IP and port configuration.')
        app.run()
    except socketerror:
        print('Address {0}:{1} already in use!'.format(
            IPWBREPLAY_HOST, IPWBREPLAY_PORT))
        sys.exit()


# Read in URI, convert to SURT
#  surt(uriIn)
# Get SURTed URI lines in CDXJ
#  Read CDXJ
#  Do bin search to find relevant lines

# read IPFS hash from relevant lines (header, payload)

# Fetch IPFS data at hashes
