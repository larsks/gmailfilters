import sys
import cliff
import cliff.app
import cliff.commandmanager

class GmailFilterApp (cliff.app.App):
    def __init__(self):
        super(GmailFilterApp, self).__init__(
            description='Gmail filtering tool',
            version='0.1',
            command_manager=cliff.commandmanager.CommandManager('gmf.cmd'),
            deferred_help=True,
        )

def main(argv=sys.argv[1:]):
    app = GmailFilterApp()
    return app.run(argv)

