import argparse
import cliff.command
import imapclient
import imaplib
import os
import xdg.BaseDirectory
import yaml

from gmailfilters import exceptions

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

default_config = os.path.join(xdg.BaseDirectory.xdg_config_home,
                              'gmailfilters.yml')

def chunker(items, chunksize):
    for i in range(0, len(items), chunksize):
        yield items[i:i+chunksize]

class BulkFilter(cliff.command.Command):
    def get_parser(self, prog_name):
        p = super(BulkFilter, self).get_parser(prog_name)

        p.add_argument('-a', '--account', default='default')
        p.add_argument('-f', '--config')
        p.add_argument('-s', '--chunksize', default=50, type=int)
        p.add_argument('-Q', '--query')
        p.add_argument('-A', '--action',
                       choices=['info', 'delete', 'flag', 'label'],
                       default='info')
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

        return p

    def take_action(self, args):
        if not args.config:
            for cfgpath in ['gmailfilter.yml', default_config]:
                self.app.LOG.info('looking for config in %s', cfgpath)
                if os.path.isfile(cfgpath):
                    args.config = cfgpath
                    break
            else:
                raise exceptions.NoConfigurationFile(
                    'Unable to find a valid configuration file')

        with open(args.config) as fd:
            config = yaml.load(fd)

        account = config['accounts'][args.account]
        server = imapclient.IMAPClient(account['host'],
                            use_uid=True,
                            ssl=account.get('ssl', True))
        server.login(account['username'], account['password'])

        if args.action == 'flag':
            add_flags = []
            del_flags = []
            for flag in args.flag:
                if flag.startswith('-'):
                    flag = flag[1:]
                    del_flags.append(getattr(imapclient, flag))
                else:
                    add_flags.append(getattr(imapclient, flag))

        for folder in args.folders:
            self.app.LOG.warning('processing folder %s', folder)

            try:
                info = server.select_folder(folder)
            except imaplib.IMAP4.error as exc:
                self.app.LOG.error('failed to select %s (%s): %s',
                              folder, type(exc), exc)
                continue

            if args.query is None:
                self.app.LOG.info('selecting all messages in %s', folder)
                messages = server.search()
            else:
                self.app.LOG.info('selecting messages in %s matching: %s',
                              folder, args.query)
                messages = server.gmail_search(args.query)

            self.app.LOG.info('found %d messages', len(messages))

            for chunk in chunker(messages, args.chunksize):
                if args.action == 'delete':
                    self.app.LOG.info('deleting messages %d...%d from %s',
                                 chunk[0], chunk[-1], folder)
                    res = server.delete_messages(chunk)
                    self.app.LOG.info('expunging messages %d...%d from %s',
                                      chunk[0], chunk[-1], folder)
                    server.expunge()
                elif args.action == 'flag':
                    self.app.LOG.info('flagging messages %d...%d from %s (%s)',
                                 chunk[0], chunk[-1], folder, flags)
                    res = server.add_flags(chunk, add_flags)
                    res = server.remove_flags(chunk, del_flags)
                elif args.action == 'label':
                    self.app.LOG.info('labelling messages %d...%d from %s (%s)',
                                 chunk[0], chunk[-1], folder, args.label)
                    res = server.add_gmail_labels(chunk, args.label)
                elif args.action == 'info':
                    self.app.LOG.info('getting info for messages %d...%d from %s',
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

