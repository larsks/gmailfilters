import cliff.command
import fnmatch

from gmailfilters import default

class BaseClientCommand(cliff.command.Command):
    def get_parser(self, prog_name):
        p = super(BaseClientCommand, self).get_parser(prog_name)
        p.add_argument('-a', '--account',
                       default='default',
                       help='Which account (from configuration file) to use')
        p.add_argument('-s', '--chunksize',
                       default=default.chunk_size,
                       type=int,
                       help='Number of messages to process at a time')

        g = p.add_argument_group('Debugging')
        g.add_argument('--debug-imap',
                       type=int,
                       default=0,
                       metavar='debug_level',
                       choices=range(6),
                       help='Enable IMAP protocol debugging')

        return p

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

    def process_folders(self, folders):
        for folder in folders:
            self.process_one_folder(folder)
