import argparse
import cliff.command
import fnmatch
import imapclient
import imaplib

from gmailfilters import exceptions

valid_flags = [
    'SEEN',
    'ANSWERED',
    'FLAGGED',
    'DELETED',
    'DRAFT',
    'RECENT',
]

headers = (
    ('from_', 'From'),
    ('reply_to', 'Reply to'),
    ('to', 'To'),
    ('cc', 'Cc'),
    ('message_id', 'Message ID'),
)

default_chunk_size = 200


def chunker(items, chunksize):
    '''Splits a list into lists of chunksize items.'''

    for i in range(0, len(items), chunksize):
        yield items[i:i+chunksize]


def labelspec(spec):
    '''Transform a list of labels, optionally prefixed with a '+' or '-',
    into a list of (action, label) tuples.'''

    if spec.startswith('-'):
        action = '-'
        value = spec[1:]
    elif spec.startswith('+'):
        action = '+'
        value = spec[1:]
    else:
        action = '+'
        value = spec

    return (action, value)


def flagspec(spec):
    '''Transform a list of imap flags into a list of (action, flag) tuples.
    This is similar to labelspec, but it validates the flags against the list
    in valid_flags.'''

    spec = spec.upper()

    action, flag = labelspec(spec)

    if flag not in valid_flags:
        raise ValueError(flag)

    return (action, getattr(imapclient, flag))


class BulkFilter(cliff.command.Command):
    def get_parser(self, prog_name):
        p = super(BulkFilter, self).get_parser(prog_name)

        p.add_argument('-a', '--account',
                       default='default',
                       help='Which account (from configuration file) to use')
        p.add_argument('-s', '--chunksize',
                       default=default_chunk_size,
                       type=int,
                       help='Number of messages to process at a time')

        g = p.add_argument_group('Filters')
        g.add_argument('-Q', '--query',
                       help='A gmail-syntax search query')
        g.add_argument('--fail-if-empty',
                       action='store_true',
                       help='Exit with an error if filter matches no messages')

        g = p.add_argument_group('Actions')
        g.add_argument('-F', '--flag',
                       action='append',
                       default=[],
                       type=flagspec,
                       help='Flag to add to or remove from messages')
        g.add_argument('-L', '--label',
                       action='append',
                       default=[],
                       type=labelspec,
                       help='Label to add to or remove from messages')
        g.add_argument('-D', '--delete',
                       action='store_true',
                       help='Delete matching messages')
        g.add_argument('-S', '--show',
                       action='store_true',
                       help='Show matching messages')

        g = p.add_argument_group('Debugging')
        g.add_argument('--debug-imap',
                       type=int,
                       default=0,
                       metavar='debug_level',
                       choices=range(6),
                       help='Enable IMAP protocol debugging')

        p.add_argument('folders', nargs='*',
                       default=['@all'])

        p.set_defaults(loglevel='WARNING')

        return p

    def show_message(self, msgid, msg):
        print '%04d: %s' % (msgid, msg['ENVELOPE'].subject)
        for header in headers:
            if not getattr(msg['ENVELOPE'], header[0], None):
                continue

            hval = getattr(msg['ENVELOPE'], header[0])
            if isinstance(hval, tuple):
                try:
                    hval = ', '.join(str(x) for x in hval)
                except TypeError:
                    hval = '...'

            print '      %s: %s' % (
                header[1], hval)
        print '      Labels: %s' % (
            ' ' .join(str(x) for x in msg['X-GM-LABELS']))
        print

    def select_folders(self, folders):
        '''Use wildcard matching to transform a list of folder names and
        patterns into a list of folder names.'''

        all_folders = self.server.list_folders()
        selected_folders = []
        for pattern in folders:
            self.app.LOG.debug('applying pattern %s', pattern)
            for folder in all_folders:
                self.app.LOG.debug('considering folder %s', folder)
                if r'\Noselect' in folder[0]:
                    self.app.LOG.debug('rejecting folder %s (noselect)', folder)
                    continue

                if pattern.startswith('@'):
                    flag = '\\' + pattern[1:].title()
                    if flag in folder[0]:
                        self.app.LOG.debug('selecting folder %s (flag)', folder)
                        selected_folders.append(folder[2])
                else:
                    if fnmatch.fnmatch(folder[2], pattern):
                        self.app.LOG.debug('selecting folder %s (pattern)', folder)
                        selected_folders.append(folder[2])

        self.app.LOG.debug('selected folders = %s', selected_folders)
        return selected_folders

    def take_action(self, args):
        self.args = args

        try:
            account = self.app.config['accounts'][args.account]
        except (TypeError, KeyError):
            raise exceptions.NoSuchAccount(
                'Unable to find account named "%s"' % args.account)

        self.server = imapclient.IMAPClient(account['host'],
                                            use_uid=True,
                                            ssl=account.get('ssl', True))
        self.server.debug = args.debug_imap

        self.server.login(account['username'], account['password'])

        selected_folders = self.select_folders(args.folders)
        if not selected_folders:
            raise exceptions.NoMatchingFolders('No folders to process')

        if args.fail_if_empty and len(selected_folders) > 1:
            raise exceptions.InvalidOptions(
                '--fail-if-empty can only be used when processing '
                'a single folder')
        self.process_folders(selected_folders)

    def process_folders(self, folders):
        for folder in folders:
            self.process_one_folder(folder)

    def process_one_folder(self, folder):
        self.app.LOG.info('processing folder %s', folder)

        try:
            info = self.server.select_folder(folder)
        except imaplib.IMAP4.error as exc:
            self.app.LOG.error('failed to select %s (%s): %s',
                          folder, type(exc), exc)
            return

        if self.args.query is None:
            self.app.LOG.info('selecting all messages in %s', folder)
            messages = self.server.search()
        else:
            self.app.LOG.info('selecting messages in %s matching: %s',
                          folder, self.args.query)
            messages = self.server.gmail_search(self.args.query)

        self.app.LOG.info('found %d messages', len(messages))

        if self.args.fail_if_empty and not messages:
            raise exceptions.NoMatchingMessages('Filter returned zero messages')

        for chunk in chunker(messages, self.args.chunksize):
            self.process_messages(folder, chunk)

    def process_messages(self, folder, chunk):
        add_flags = [flag[1] for flag in self.args.flag if flag[0] == '+']
        del_flags = [flag[1] for flag in self.args.flag if flag[0] == '-']
        add_labels = [label[1] for label in self.args.label if label[0] == '+']
        del_labels = [label[1] for label in self.args.label if label[0] == '-']

        if self.args.flag:
            self.app.LOG.info('applying flags to  messages %d...%d from %s (%s)',
                         chunk[0], chunk[-1], folder, self.args.flag)
            res = self.server.add_flags(chunk, add_flags)
            res = self.server.remove_flags(chunk, del_flags)

        if self.args.label:
            self.app.LOG.info('labelling messages %d...%d from %s (%s)',
                         chunk[0], chunk[-1], folder, self.args.label)
            res = self.server.add_gmail_labels(chunk, add_labels)
            res = self.server.remove_gmail_labels(chunk, del_labels)

        if self.args.show:
            self.app.LOG.info('getting info for messages %d...%d from %s',
                         chunk[0], chunk[-1], folder)
            res = self.server.fetch(chunk, data=['ENVELOPE', 'X-GM-LABELS'])
            for msg in sorted(res.keys()):
                self.show_message(msg, res[msg])

        if self.args.delete:
            self.app.LOG.info('deleting messages %d...%d from %s',
                         chunk[0], chunk[-1], folder)
            res = self.server.delete_messages(chunk)
            self.app.LOG.info('expunging messages %d...%d from %s',
                              chunk[0], chunk[-1], folder)
            self.server.expunge()
