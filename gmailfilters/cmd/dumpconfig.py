import cliff.command
import yaml
import sys


class DumpConfig(cliff.command.Command):
    def take_action(self, args):
        yaml.dump(self.app.config,
                  stream=sys.stdout,
                  default_flow_style=False)
