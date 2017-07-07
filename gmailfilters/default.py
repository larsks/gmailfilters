import os
import xdg.BaseDirectory

chunk_size = 200
config_path = os.path.join(xdg.BaseDirectory.xdg_config_home,
                           'gmailfilters.yml')

