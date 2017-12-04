import argparse
import cliff.command
import imapclient
import imaplib
import yaml

from gmailfilters import exceptions
from gmailfilters import default
from gmailfilters.cmd.baseclient import BaseClientCommand
from gmailfilters.util import chunker

class ApplyFilters(BaseClientCommand):
    def get_parser(self, prog_name):
        p = super(ApplyFilters, self).get_parser(prog_name)

        g = p.add_argument_group('Filters')
        g.add_argument('--skip-smartlabels', '-S',
                       action='store_true',
                       help='Ignore smartlabel filters')

        p.add_argument('filters',
                       help='Filters in YAML syntax')
        p.add_argument('folders', nargs='*',
                       default=['@all'])

        return p

    def build_filters(self, filters):
        _filters = []
        for filter in filters:
            _query = []
            if 'hasTheWord' in filter:
                if '^smartlabel' in filter['hasTheWord'] and self.args.skip_smartlabels:
                    continue

                _query.append(filter['hasTheWord'])

            for kw in ['from', 'subject', 'to']:
                if kw in filter:
                    _query.append(kw + ':' + filter[kw])

            _query = ' '.join(_query)
            filter['query'] = _query
            _filters.append(filter)

        return _filters

    def take_action(self, args):
        self.args = args

        try:
            account = self.app.config['accounts'][args.account]
        except (TypeError, KeyError):
            raise exceptions.NoSuchAccount(
                'Unable to find account named "%s"' % args.account)

        with open(args.filters) as fd:
            filters = yaml.load(fd)

        self.filters = self.build_filters(filters)

        self.server = imapclient.IMAPClient(account['host'],
                                            use_uid=True,
                                            ssl=account.get('ssl', True))
        self.server.debug = args.debug_imap

        self.server.login(account['username'], account['password'])

        selected_folders = self.select_folders(args.folders)
        if not selected_folders:
            raise exceptions.NoMatchingFolders('No folders to process')

        self.process_folders(selected_folders)

    def process_one_folder(self, folder):
        self.app.LOG.info('processing folder %s', folder)

        try:
            info = self.server.select_folder(folder)
        except imaplib.IMAP4.error as exc:
            self.app.LOG.error('failed to select %s (%s): %s',
                          folder, type(exc), exc)
            return

        for filter in self.filters:
            self.app.LOG.info('selecting messages in %s matching: %s',
                          folder, filter['query'])
            messages = self.server.gmail_search(filter['query'])
            self.app.LOG.info('found %d messages', len(messages))

            for chunk in chunker(messages, self.args.chunksize):
                self.process_messages(folder, filter, chunk)

    def process_messages(self, folder, filter, chunk):
        for k, v in list(filter.items()):
            if k in ['query', 'hasTheWord', 'to', 'from', 'subject']:
                continue
            elif k == 'label':
                labels = v.split()
                self.app.LOG.info('labelling messages %d...%d from %s (%s)',
                             chunk[0], chunk[-1], folder, labels)
                res = self.server.add_gmail_labels(chunk, labels)
            elif k == 'shouldMarkAsread' and v:
                self.app.LOG.info('marking messages %d...%d as read from %s',
                             chunk[0], chunk[-1], folder)
                res = self.server.add_flags(chunk, imapclient.SEEN)
            elif k == 'shouldArchive' and v:
                self.app.LOG.info('archiving messages %d...%d as read from %s',
                             chunk[0], chunk[-1], folder)
                res = self.server.remove_gmail_labels(chunk, '\\Inbox')
            elif k == 'shouldTrash' and v:
                self.app.LOG.info('deleting messages %d...%d from %s',
                             chunk[0], chunk[-1], folder)
                res = self.server.delete_messages(chunk)
                self.app.LOG.info('expunging messages %d...%d from %s',
                                  chunk[0], chunk[-1], folder)
                self.server.expunge()
            else:
                self.app.LOG.warn('ignoring unsupported action: %s (%s)',
                                  k, v)
