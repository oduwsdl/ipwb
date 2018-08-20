import sys
import os
import argparse
import string  # For generating a temp file for stdin
import random  # For generating a temp file for stdin

from .__init__ import __version__ as ipwbVersion
from .util import INDEX_FILE


# ipwb modules
from . import replay
from . import indexer
from . import util

from .util import IPFSAPI_HOST, IPFSAPI_PORT, IPWBREPLAY_HOST, IPWBREPLAY_PORT


def main():
    util.checkForUpdate()
    args = checkArgs(sys.argv)


def checkArgs_index(args):
    if not util.isDaemonAlive():
        sys.exit()
    encKey = None
    compressionLevel = None
    if args.e:
        encKey = ''
    if args.c:
        compressionLevel = 6  # Magic 6, TA-DA!

    indexer.indexFileAt(args.warcPath, encKey, compressionLevel,
                        args.compressFirst, outfile=args.outfile,
                        debug=args.debug)


def checkArgs_replay(args):
    suppliedIndexParameter = hasattr(args, 'index') and args.index is not None
    likelyPiping = not sys.stdin.isatty()

    if not suppliedIndexParameter and likelyPiping:
        cdxjIn = ''.join(sys.stdin.readlines())
        if len(cdxjIn) == 0:  # Daemon was not running, so nothing was indexed
            print(('ERROR: The IPFS daemon must be running to pipe input from'
                  ' the indexer to the replay system.'))
            sys.exit()

        random.seed()
        # Write data to temp file (sub-optimal)
        tempFilePath = '/tmp/' + ''.join(random.sample(
              string.ascii_uppercase + string.digits * 6, 12)) + '.cdxj'
        with open(tempFilePath, 'w') as f:
            f.write(cdxjIn)
        args.index = tempFilePath
        suppliedIndexParameter = True

    proxy = None
    if hasattr(args, 'proxy') and args.proxy is not None:
        print('Proxying to ' + args.proxy)
        proxy = args.proxy

    # TODO: add any other sub-arguments for replay here
    if suppliedIndexParameter:
        replay.start(cdxjFilePath=args.index, proxy=proxy)
    else:
        print('ERROR: An index file must be specified if not piping, e.g.,')
        print('> ipwb replay /path/to/your/index.cdxj\n')

        args.onError()
        sys.exit()


def checkArgs(argsIn):
    """
    Check to ensure valid arguments were passed in and provides guidance
    on the available options if not
    """
    parser = argparse.ArgumentParser(
        description='InterPlanetary Wayback (ipwb)', prog="ipwb")
    subparsers = parser.add_subparsers(
        title="ipwb commands",
        description=("Invoke using \"ipwb <command>\""
                     ", e.g., ipwb replay <cdxjFile>"))

    indexParser = subparsers.add_parser(
        'index',
        prog="ipwb",
        description="Index a WARC file for replay in ipwb",
        help="Index a WARC file for replay in ipwb")
    indexParser.add_argument(
        'warcPath',
        help="Path to a WARC[.gz] file",
        metavar="index <warcPath>",
        nargs='+',
        default=None)
    indexParser.add_argument(
        '-e',
        help="Encrypt WARC content prior to adding to IPFS",
        action='store_true',
        default=False)
    indexParser.add_argument(
        '-c',
        help='Compress WARC content prior to adding to IPFS',
        action='store_true',
        default=False)
    indexParser.add_argument(
        '--compressFirst',
        help='Compress data before encryption, where applicable',
        action='store_true',
        default=False)
    indexParser.add_argument(
        '-o', '--outfile',
        help='Path to an output CDXJ file, defaults to STDOUT',
        default=None)
    indexParser.add_argument(
        '--debug',
        help='Convenience flag to help with testing and debugging',
        action='store_true',
        default=False)
    indexParser.set_defaults(func=checkArgs_index)

    replayParser = subparsers.add_parser(
        'replay',
        prog="ipwb replay",
        description="Start the ipwb relay system",
        help="Start the ipwb replay system")
    replayParser.add_argument(
        'index',
        help='path, URI, or multihash of file to use for replay',
        nargs='?')
    replayParser.add_argument(
        '-P', '--proxy',
        help='Proxy URL',
        metavar='<host:port>',
        nargs='?')
    replayParser.set_defaults(func=checkArgs_replay,
                              onError=replayParser.print_help)

    parser.add_argument(
        '-d', '--daemon',
        help='Location of ipfs daemon (default 127.0.0.1:5001)',
        default='{0}:{1}'.format(IPFSAPI_HOST, IPFSAPI_PORT),
        dest='daemon_address')
    parser.add_argument(
        '-v', '--version', help='Report the version of ipwb', action='version',
        version='InterPlanetary Wayback ' + ipwbVersion)

    argCount = len(argsIn)
    cmdList = ['index', 'replay']
    baseParserFlagList = ['-d', '--daemon', '-v', '--version']

    # Various invocation error, used to show appropriate help
    cmdError_index = argCount == 2 and argsIn[1] == 'index'
    cmdError_noCommand = argCount == 1
    cmdError_invalidCommand = argCount > 1 \
        and argsIn[1] not in cmdList + baseParserFlagList

    if cmdError_noCommand or cmdError_invalidCommand:
        parser.print_help()
        sys.exit()
    elif cmdError_index:
        indexParser.print_help()
        sys.exit()

    results = parser.parse_args()
    results.func(results)

    return results


if __name__ == "__main__":
    main()
