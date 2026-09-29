"""
scripts/backup.py - 备份脚本
支持 SQLite/MySQL 数据库备份，以及 data/ 目录备份。
"""

from __future__ import annotations

import os
import shutil
import datetime
import tarfile
import tempfile
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
BACKUP_DIR = PROJECT_ROOT / "backups"


def _timestamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def backup_sqlite(db_path: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_path, dest)
    return dest


def backup_mysql(database_url: str, dest: Path) -> Path:
    # 可选：如需 MySQL 备份，请安装并配置 mysqldump
    raise NotImplementedError("MySQL backup requires mysqldump configured in environment.")


def backup_data_dir(dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(dest, "w:gz") as tar:
        for item in DATA_DIR.rglob("*"):
            if item.is_file():
                tar.add(item, arcname=item.relative_to(DATA_DIR))
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup ISSF knowledge base data")
    parser.add_argument("--db-url", default=os.getenv("DATABASE_URL", ""), help="Database URL")
    parser.add_argument("--include-data", action="store_true", help="Also backup data/ directory")
    args = parser.parse_args()

    BACKUP_DIR.mkdir(exist_ok=True)
    base_name = BACKUP_DIR / f"backup_{_timestamp()}"

    if args.db_url:
        if args.db_url.startswith("sqlite"):
            db_file = Path(args.db_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", ""))
            if db_file.exists():
                backup_dest = base_name.with_suffix(".db.gz" if args.include_data else ".db")
                backup_sqlite(db_file, backup_dest)
                print(f"SQLite backup saved: {backup_dest}")
            else:
                print("SQLite database not found, skipped.")
        else:
            try:
                backup_mysql(args.db_url, base_name.with_suffix(".sql.gz"))
            except NotImplementedError:
                print("MySQL backup not configured, skipped.")

    if args.include_data and DATA_DIR.exists():
        data_backup = base_name.with_suffix(".data.tar.gz")
        backup_data_dir(data_backup)
        print(f"Data dir backup saved: {data_backup}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
