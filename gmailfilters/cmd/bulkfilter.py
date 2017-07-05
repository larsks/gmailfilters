import argparse
import imaplib
import imapclient
import yaml
import logging

valid_flags = [
    'SEEN',
    'ANSWERED',
    'DRAFT',
    'DELETED',
    'FLAGGED',
    'SEEN',
]

headers = (
    ('from_', 'From'),
    ('reply_to', 'Reply to'),
    ('to', 'To'),
    ('cc', 'Cc'),
    ('message_id', 'Message ID'),
)

def chunker(items, chunksize):
    for i in range(0, len(items), chunksize):
        yield items[i:i+chunksize]

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('-a', '--account', default='default')
    p.add_argument('-f', '--config', default='config.yml')
    p.add_argument('-s', '--chunksize', default=50, type=int)
    p.add_argument('-q', '--query')
    p.add_argument('-A', '--action',
                   choices=['info', 'delete', 'flag', 'label'],
                   default='info',
                   required=True)
    p.add_argument('-F', '--flag',
                   action='append',
                   default=[],
                   choices=valid_flags)
    p.add_argument('-L', '--label',
                   action='append',
                   default=[])
    p.add_argument('-v', '--verbose',
                   dest='loglevel',
                   action='store_const',
                   const='INFO')

    p.add_argument('folders', nargs='*', default=[])

    p.set_defaults(loglevel='WARNING')

    return p.parse_args()

def main():
    args = parse_args()
    logging.basicConfig(level=args.loglevel)

    with open(args.config) as fd:
        config = yaml.load(fd)

    account = config['accounts'][args.account]
    server = imapclient.IMAPClient(account['host'],
                        use_uid=True,
                        ssl=account.get('ssl', True))
    server.login(account['username'], account['password'])

    flags = []
    for flag in args.flag:
        flags.append(getattr(imapclient, flag))

    for folder in args.folders:
        logging.warning('processing folder %s', folder)

        try:
            info = server.select_folder(folder)
        except imaplib.IMAP4.error as exc:
            logging.error('failed to select %s (%s): %s',
                          folder, type(exc), exc)
            continue

        if args.query is None:
            messages = server.search()
        else:
            messages = server.gmail_search(args.query)

        for chunk in chunker(messages, args.chunksize):
            if args.action == 'delete':
                logging.info('deleting messages %d:%d from %s',
                             chunk[0], chunk[-1], folder)
                res = server.delete_messages(chunk)
            elif args.action == 'flag':
                logging.info('flagging messages %d:%d from %s (%s)',
                             chunk[0], chunk[-1], folder, flags)
                res = server.add_flags(chunk, flags)
            elif args.action == 'label':
                logging.info('labelling messages %d:%d from %s (%s)',
                             chunk[0], chunk[-1], folder, args.labels)
                res = server.add_gmail_labels(chunk, args.labels)
            elif args.action == 'info':
                logging.info('getting info for messages %d:%d from %s',
                             chunk[0], chunk[-1], folder)
                res = server.fetch(chunk, data=['INTERNALDATE', 'FLAGS', 'ENVELOPE'])
                for msg in sorted(res.keys()):
                    print '%04d: %s' % (msg, res[msg]['ENVELOPE'].subject)
                    for header in headers:
                        if not getattr(res[msg]['ENVELOPE'], header[0], None):
                            continue

                        hval = getattr(res[msg]['ENVELOPE'], header[0])
                        if isinstance(hval, tuple):
                            try:
                                hval = ', '.join(str(x) for x in hval)
                            except TypeError:
                                hval = '...'

                        print '      %s: %s' % (
                            header[1], hval)
                    print

            logging.info('expunging messages %d:%d from %s', chunk[0], chunk[-1], folder)
            server.expunge()

if __name__ == '__main__':
    main()
