import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if getattr(sys, 'frozen', False):
    RUN_DATA_DIR = os.path.join(os.environ['LOCALAPPDATA'], 'FileGraph')
    DB_PATH = os.path.join(RUN_DATA_DIR, 'database.db')
    CONFIG_DIR = os.path.join(RUN_DATA_DIR, 'config')
    LOG_DIR = os.path.join(RUN_DATA_DIR, 'logs')
else:
    RUN_DATA_DIR = os.path.join(BASE_DIR, 'db')
    DB_PATH = os.path.join(RUN_DATA_DIR, 'database.db')
    CONFIG_DIR = os.path.join(BASE_DIR, 'config')
    LOG_DIR = os.path.join(BASE_DIR, 'logs')

os.makedirs(RUN_DATA_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

TEMPLATE_DB = os.path.join(BASE_DIR, 'db', 'template_db.db')
if not os.path.exists(DB_PATH) and os.path.exists(TEMPLATE_DB):
    import shutil
    shutil.copy(TEMPLATE_DB, DB_PATH)