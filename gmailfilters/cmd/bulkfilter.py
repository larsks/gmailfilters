import argparse
import cliff.command
import fnmatch
import imapclient
import imaplib
import os
import xdg.BaseDirectory
import yaml

from gmailfilters import exceptions

valid_pos_flags = [
    'SEEN',
    'ANSWERED',
    'FLAGGED',
    'DELETED',
    'DRAFT',
    'RECENT',
]

valid_neg_flags = ['-' + x for x in valid_pos_flags]

valid_flags = valid_pos_flags + valid_neg_flags

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

        p.add_argument('-a', '--account',
                       default='default',
                       help='Which account (from configuration file) to use')
        p.add_argument('-f', '--config',
                       help='Path to configuration file')
        p.add_argument('-s', '--chunksize',
                       default=50,
                       type=int,
                       help='Number of messages to process at a time')
        p.add_argument('-Q', '--query',
                       help='A gmail-syntax search query')
        p.add_argument('-A', '--action',
                       choices=['info', 'delete', 'flag', 'label'],
                       default='info',
                       help='Which action to perform')
        p.add_argument('-F', '--flag',
                       action='append',
                       default=[],
                       choices=valid_flags,
                       help='Flag to add to or remove from messages')
        p.add_argument('-L', '--label',
                       action='append',
                       default=[],
                       help='Label to add to message')

        p.add_argument('folders', nargs='*', default=['[Gmail]/All Mail'])

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

        all_folders = server.list_folders()
        selected_folders = []
        for pattern in args.folders:
            for folder in all_folders:
                if r'\Noselect' in folder[0]:
                    continue

                if fnmatch.fnmatch(folder[2], pattern):
                    selected_folders.append(folder[2])

        for folder in selected_folders:
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
                    if add_flags:
                        self.app.LOG.info('adding flags to  messages %d...%d from %s (%s)',
                                     chunk[0], chunk[-1], folder, add_flags)
                        res = server.add_flags(chunk, add_flags)
                    if del_flags:
                        self.app.LOG.info('removing flags from  messages %d...%d from %s (%s)',
                                     chunk[0], chunk[-1], folder, del_flags)
                    res = server.remove_flags(chunk, del_flags)
                elif args.action == 'label':
                    self.app.LOG.info('labelling messages %d...%d from %s (%s)',
                                 chunk[0], chunk[-1], folder, args.label)
                    res = server.add_gmail_labels(chunk, args.label)
                elif args.action == 'info':
                    self.app.LOG.info('getting info for messages %d...%d from %s',
                                 chunk[0], chunk[-1], folder)
                    res = server.fetch(chunk, data=['ENVELOPE', 'FLAGS', 'X-GM-LABELS'])
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
                        print '      Labels: %s' % (
                            ' ' .join(str(x) for x in res[msg]['X-GM-LABELS']))
                        print

