import argparse
import os
import random  # For generating a temp file for stdin
# import string  # For generating a temp file for stdin
import sys
import tempfile

from multiaddr import Multiaddr
from multiaddr import exceptions as multiaddr_exceptions
# ipwb modules
from ipwb import settings, replay, indexer, util
from ipwb.error_handler import exception_logger
from ipwb.__init__ import __version__ as ipwb_version


@exception_logger(catch=not settings.DEBUG)
def main():
    check_args(sys.argv)


def check_args_index(args):
    # args.daemon_address is always set. Either default or by CLI
    try:
        # see if it parses
        daemon = Multiaddr(args.daemon_address)
    except multiaddr_exceptions.StringParseError as e:
        print("Daemon address cannot be parsed")
        raise e
    settings.App.set("ipfsapi", str(daemon))

    util.check_daemon_is_alive()

    enc_key = None
    compression_level = None
    if args.e:
        enc_key = ''
    if args.c:
        compression_level = 6  # Magic 6, TA-DA!

    indexer.index_file_at(args.warc_path, enc_key, compression_level,
                          args.compressFirst, outfile=args.outfile,
                          debug=args.debug)


def check_args_replay(args):
    supplied_index_parameter = hasattr(args, 'index') and \
                               args.index is not None
    likely_piping = not sys.stdin.isatty()

    if not supplied_index_parameter and likely_piping:
        cdxj_in = ''.join(sys.stdin.readlines())
        if len(cdxj_in) == 0:  # Daemon was not running, so nothing was indexed
            print(('ERROR: The IPFS daemon must be running to pipe input from'
                  ' the indexer to the replay system.'))
            sys.exit()

        random.seed()
        # Write data to temp file (sub-optimal)

        fh, args.index = tempfile.mkstemp(suffix='.cdxj')
        os.close(fh)
        with open(args.index, 'w') as f:
            f.write(cdxj_in)

        supplied_index_parameter = True

    proxy = None
    if hasattr(args, 'proxy') and args.proxy is not None:
        print(f'Proxying to {args.proxy}')
        proxy = args.proxy
    try:
        # see if it parses
        daemon = Multiaddr(args.daemon_address)
    except multiaddr_exceptions.StringParseError as e:
        print("Daemon address cannot be parsed")
        raise e
    settings.App.set("ipfsapi", str(daemon))

    port = replay.IPWBREPLAY_PORT
    if hasattr(args, 'port') and args.port is not None:
        print(f'Using custom port {args.port} for replay.')
        port = args.port

    # TODO: add any other sub-arguments for replay here
    if supplied_index_parameter:
        replay.start(cdxj_file_path=args.index, proxy=proxy, port=port)
    else:
        print('ERROR: An index file must be specified if not piping, e.g.,')
        print(("> ipwb replay "
               f"{os.path.join('path', 'to', 'your', 'index.cdxj')}\n"))

        args.onError()
        sys.exit()


def check_args(args_in):
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

    index_parser = subparsers.add_parser(
        'index',
        prog="ipwb",
        description="Index a WARC file for replay in ipwb",
        help="Index a WARC file for replay in ipwb")
    index_parser.add_argument(
        'warc_path',
        help="Path to a WARC[.gz] file",
        metavar="index <warc_path>",
        nargs='+',
        default=None)
    index_parser.add_argument(
        '-e',
        help="Encrypt WARC content prior to adding to IPFS",
        action='store_true',
        default=False)
    index_parser.add_argument(
        '-c',
        help='Compress WARC content prior to adding to IPFS',
        action='store_true',
        default=False)
    index_parser.add_argument(
        '--compressFirst',
        help='Compress data before encryption, where applicable',
        action='store_true',
        default=False)
    index_parser.add_argument(
        '-o', '--outfile',
        help='Path to an output CDXJ file, defaults to STDOUT',
        default=None)
    index_parser.add_argument(
        '--debug',
        help='Convenience flag to help with testing and debugging',
        action='store_true',
        default=False)
    index_parser.set_defaults(func=check_args_index)

    replay_parser = subparsers.add_parser(
        'replay',
        prog="ipwb replay",
        description="Start the ipwb relay system",
        help="Start the ipwb replay system")
    replay_parser.add_argument(
        'index',
        help='path, URI, or multihash of file to use for replay',
        nargs='?')
    replay_parser.add_argument(
        '-P', '--proxy',
        help='Proxy URL',
        metavar='<host:port>',
        nargs='?')
    replay_parser.add_argument(
        '-p', '--port',
        help='Custom Port',
        type=int,
        default=util.IPWBREPLAY_PORT
    )
    replay_parser.set_defaults(func=check_args_replay,
                               onError=replay_parser.print_help)

    parser.add_argument(
        '-d', '--daemon',
        help=("Multi-address of IPFS daemon "
              "(default /dns/localhost/tcp/5001/http)"),
        default=settings.App.config("ipfsapi"),
        dest='daemon_address')
    parser.add_argument(
        '-v', '--version', help='Report the version of ipwb', action='version',
        version=f'InterPlanetary Wayback {ipwb_version}')
    parser.add_argument(
        '-u', '--update-check',
        action='store_true',
        help='Check whether an updated version of ipwb is available'
        )
    parser.set_defaults(func=util.check_for_update)

    arg_count = len(args_in)
    cmd_list = ['index', 'replay']
    base_parser_flag_list = ['-d', '--daemon', '-v', '--version',
                             '-u', '--update-check']

    # Various invocation error, used to show appropriate help
    cmd_error_index = arg_count == 2 and args_in[1] == 'index'
    cmd_error_no_command = arg_count == 1
    cmd_error_invalid_command = arg_count > 1 \
        and args_in[1] not in cmd_list + base_parser_flag_list

    if cmd_error_no_command or cmd_error_invalid_command:
        parser.print_help()
        sys.exit()
    elif cmd_error_index:
        index_parser.print_help()
        sys.exit()

    results = parser.parse_args()
    results.func(results)

    return results


if __name__ == "__main__":
    main()
