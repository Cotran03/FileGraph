import os
import sys

from core.database_manager import DatabaseManager
from gui.main_window import MainWindow


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_runtime_paths() -> dict[str, str]:
    if getattr(sys, "frozen", False):
        run_data_dir = os.path.join(os.environ["LOCALAPPDATA"], "FileGraph")
        config_dir = os.path.join(run_data_dir, "config")
        log_dir = os.path.join(run_data_dir, "logs")
    else:
        run_data_dir = os.path.join(BASE_DIR, "db")
        config_dir = os.path.join(BASE_DIR, "config")
        log_dir = os.path.join(BASE_DIR, "logs")

    return {
        "run_data_dir": run_data_dir,
        "db_path": os.path.join(run_data_dir, "database.db"),
        "config_dir": config_dir,
        "log_dir": log_dir,
    }


def initialize_runtime() -> dict[str, str]:
    paths = get_runtime_paths()
    os.makedirs(paths["run_data_dir"], exist_ok=True)
    os.makedirs(paths["config_dir"], exist_ok=True)
    os.makedirs(paths["log_dir"], exist_ok=True)

    template_db = os.path.join(BASE_DIR, "db", "template_db.db")
    if not os.path.exists(paths["db_path"]) and os.path.exists(template_db):
        import shutil

        shutil.copy(template_db, paths["db_path"])

    with DatabaseManager(paths["db_path"]) as database:
        database.init_db()

    return paths


def run() -> int:
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    paths = initialize_runtime()
    app = QApplication(sys.argv)
    icon_path = os.path.join(BASE_DIR, "assets", "app.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    window = MainWindow(paths["db_path"])
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
