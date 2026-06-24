import os
import sys

APP_NAME = "Inventra"
APP_VERSION = "2.1.15"
COMPANY = "toshfry"

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, "data")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
EXPORT_DIR = os.path.join(BASE_DIR, "exports")

for d in [DATA_DIR, BACKUP_DIR, EXPORT_DIR]:
    os.makedirs(d, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "inventra.db")

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 820
MIN_WIDTH = 1024
MIN_HEIGHT = 640

CACHE_TTL = 60
