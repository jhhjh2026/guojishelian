"""
scripts/migrate.py - 数据库迁移脚本
运行方式：
  python scripts/migrate.py upgrade
  python scripts/migrate.py downgrade -1
  python scripts/migrate.py current
"""
from __future__ import annotations

import sys
from pathlib import Path
from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
config = Config(str(PROJECT_ROOT / "alembic.ini"))
config.set_main_option("script_location", str(PROJECT_ROOT / "backend" / "app" / "db" / "migrations"))


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/migrate.py <upgrade|downgrade|current|history>")
        return 1
    cmd = sys.argv[1]
    args = sys.argv[2:]
    if cmd == "upgrade":
        revision = args[0] if args else "head"
        command.upgrade(config, revision)
    elif cmd == "downgrade":
        revision = args[0] if args else "-1"
        command.downgrade(config, revision)
    elif cmd == "current":
        command.current(config)
    elif cmd == "history":
        command.history(config)
    else:
        print(f"Unknown command: {cmd}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
