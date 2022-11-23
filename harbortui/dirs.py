from pathlib import Path

from appdirs import AppDirs

from .__about__ import APP_NAME, AUTHOR, __version__

appdir = AppDirs(APP_NAME, AUTHOR)

CONFIG_DIR = Path(appdir.user_config_dir)
LOGS_DIR = Path(appdir.user_log_dir)
