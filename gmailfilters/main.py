import cliff
import cliff.app
import cliff.commandmanager
import os
import sys
import yaml

from gmailfilters import default

class GmailFilterApp (cliff.app.App):
    def __init__(self):
        super(GmailFilterApp, self).__init__(
            description='Gmail filtering tool',
            version='0.1',
            command_manager=cliff.commandmanager.CommandManager('gmf.cmd'),
            deferred_help=True,
        )

    def build_option_parser(self, *args, **kwargs):
        p = super(GmailFilterApp, self).build_option_parser(*args, **kwargs)

        p.add_argument('--config', '-f',
                     help='Path to configuration file')

        return p

    def initialize_app(self, argv):
        if not self.options.config:
            for cfgpath in ['gmailfilters.yml', default.config_path]:
                self.LOG.debug('looking for config in %s', cfgpath)
                if os.path.isfile(cfgpath):
                    self.options.config = cfgpath
                    break

        if self.options.config:
            self.LOG.debug('reading configuration from %s',
                               self.options.config)
            with open(self.options.config) as fd:
                self.config = yaml.safe_load(fd)


def main(argv=sys.argv[1:]):
    app = GmailFilterApp()
    return app.run(argv)

